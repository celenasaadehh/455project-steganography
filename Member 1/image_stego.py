from __future__ import annotations
import argparse
from dataclasses import asdict, dataclass
from getpass import getpass
import hashlib
from io import BytesIO
import json
import math
import os
from pathlib import Path
import struct
import subprocess
from tempfile import TemporaryDirectory
import warnings
import zlib

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_FILE = 40 * 1024 * 1024
MAX_PIXELS = 25_000_000
MAX_MSG = 2 * 1024 * 1024
FORMATS = ('PNG','BMP','JPEG','HEIF')
MAGIC = b'ILAB'
VERSION = 1
_HEADER = struct.Struct('>4sBBBI16s12s')
HEADER_BYTES = _HEADER.size + 4
STEP = 48
HDR_REPEATS = 3
BODY_REPEATS = 2
_ROOT = Path(__file__).resolve().parent
_HEIF_BRANDS = {b'heic',b'heix',b'hevc',b'hevx',b'heim',b'heis',b'hevm',b'hevs',b'mif1',b'msf1'}
try:
    from pillow_heif import register_heif_opener
except ImportError:
    _PIL_HEIF = False
else:
    register_heif_opener(thumbnails=False, depth_images=False, aux_images=False)
    _PIL_HEIF = True

class StegoError(ValueError): pass
class ImageError(StegoError): pass
class CapacityError(StegoError): pass
class PayloadError(StegoError): pass
class PasswordError(StegoError): pass
class DependencyError(StegoError): pass

@dataclass(frozen=True)
class Capacity:
    input_format: str
    output_format: str
    mode: str
    width: int
    height: int
    max_message_bytes: int
    encrypted: bool
    can_embed: bool
    jpeg_normalized: bool

@dataclass(frozen=True)
class EmbedResult:
    image: bytes
    output_format: str
    media_type: str
    mode: str
    message_bytes: int
    capacity_bytes: int
    jpeg_normalized: bool

@dataclass(frozen=True)
class Quality:
    mse: float
    psnr_db: float | None
    changed_rgb_fraction: float
    width: int
    height: int


def _validate_blob(data):
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_FILE:
        raise ImageError('Expected nonempty image bytes up to 40 MiB.')

# Opens photo, checks format and size, and corrects its orientation
def _load(data: bytes):
    _validate_blob(data)
    header = data[:256]
    heif = header[4:8] == b'ftyp' and any(header[i:i+4] in _HEIF_BRANDS for i in range(8,len(header),4) if i != 12)
    try:
        if heif and not _PIL_HEIF:
            from support.heic_native import decode
            return decode(data, MAX_PIXELS), 'HEIF', 1
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as im:
                fmt = im.format
                if fmt not in FORMATS:
                    raise ImageError(f'Unsupported image type: {fmt}. Use PNG, BMP, JPEG or HEIC/HEIF.')
                if im.width*im.height > MAX_PIXELS or max(im.size)>12000:
                    raise ImageError('Image exceeds 25 megapixels or 12,000 pixels on one side.')
                if fmt != 'HEIF' and getattr(im, 'n_frames', 1) != 1:
                    raise ImageError('Only still images are supported.')
                orientation = im.getexif().get(274, 1)
                norm = ImageOps.exif_transpose(im)
                alpha = 'A' in norm.getbands() or 'transparency' in norm.info
                return norm.convert('RGBA' if alpha else 'RGB'), fmt, orientation
    except StegoError:
        raise
    except RuntimeError as exc:
        raise DependencyError(str(exc)) from exc
    except (OSError, ValueError, OverflowError, UnidentifiedImageError,
            Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ImageError(f'Cannot decode image: {exc}') from exc


def _output(fmt):
    if not isinstance(fmt,str): raise ImageError('Output format must be PNG, BMP or JPEG.')
    fmt = fmt.upper()
    if fmt == 'JPG': fmt = 'JPEG'
    if fmt not in ('PNG','BMP','JPEG'):
        raise ImageError('Choose PNG, BMP or JPEG for output. HEIC/HEIF is input only.')
    return fmt


def _icc(im):
    profile = im.info.get('icc_profile')
    return {'icc_profile':profile} if isinstance(profile,bytes) and profile[16:20] == b'RGB ' else {}


def _save(im, fmt, **kwargs):
    buf = BytesIO()
    im.save(buf, fmt, **kwargs)
    if buf.tell() > MAX_FILE: raise ImageError('Generated carrier exceeds the 40 MiB upload limit.')
    return buf.getvalue()


def _helper():
    name = 'jpegtool.exe' if os.name=='nt' else 'jpegtool'
    configured = os.environ.get('STEGO_JPEG_TOOL')
    paths = [Path(configured).expanduser()] if configured else [_ROOT/'build'/name,_ROOT/'build'/'Release'/name]
    for path in paths:
        if path.is_file() and os.access(path,os.X_OK): return str(path.resolve())
    raise DependencyError('Build jpegtool with CMake (README) or set STEGO_JPEG_TOOL.')


def _run(*args):
    try:
        proc = subprocess.run([_helper(), *map(str,args)], check=False, capture_output=True, timeout=35)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DependencyError('JPEG coefficient helper could not run.') from exc
    if proc.returncode:
        raise ImageError('JPEG coefficient helper rejected the image or encoding.')

class _Jpeg:
    ident = 2
    name = 'jpeg-dct-qim-ecc'
    # Helper function that reads the stored DCT coefficients (patterns in JPEG blocks)
    def __init__(self, data):
        self.data = data
        with TemporaryDirectory() as d:
            src, out = Path(d)/'in.jpg', Path(d)/'coeff.bin'
            src.write_bytes(data)
            _run('read',src,out)
            raw = out.read_bytes()
        if len(raw)<24: raise ImageError('Truncated JPEG coefficient data.')
        w,h,*q = struct.unpack_from('<6I',raw)
        if len(raw) != 24 + 8*w*h or min(q)<1:
            raise ImageError('Inconsistent JPEG coefficient data.')
        self.q = np.array(q, dtype=np.int32)
        self.co = np.frombuffer(raw,dtype='<i2',offset=24).copy()
        self.blocks = (w,h)
        self.hn = HEADER_BYTES*16*HDR_REPEATS
        self.slots = len(self.co)
        self.order = _rank(b'jpeg-public-header-v1'+struct.pack('>II',w,h),self.slots)

    def fit(self, n):
        return self.slots >= self.hn + n*16*BODY_REPEATS

    def max_body(self):
        return max(0,(self.slots-self.hn)//(16*BODY_REPEATS))

    def _route(self, n, seed, header):
        repeats = HDR_REPEATS if header else BODY_REPEATS
        if header:
            idx = self.order[:n*16*repeats]
        else:
            rest = self.order[self.hn:]
            idx = rest[_rank(seed+b'/jpeg/route',len(rest),n*16*repeats)]
        dither = (_rng(seed+b'/jpeg/dither').random_raw(len(idx)) % STEP).astype(np.int32)
        return idx, dither, repeats

    def write(self,data,seed,header=False):
        idx,dither,repeats = self._route(len(data),seed,header)
        bits = np.tile(_ecc_encode(data),repeats).astype(np.int32)
        q = self.q[idx%4]
        x = self.co[idx].astype(np.int32)*q
        offset = dither + bits*STEP
        target = offset + 2*STEP * ((x-offset+STEP)//(2*STEP))
        quantized = (2*target+q)//(2*q)
        if np.any(np.abs(quantized)>1023):
            raise ImageError('JPEG contains a coefficient outside the supported embedding range.')
        self.co[idx] = quantized

    def read(self,n,seed,header=False):
        idx,dither,repeats = self._route(n,seed,header)
        if not len(idx): return b''
        x = self.co[idx].astype(np.int32)*self.q[idx%4] - dither
        score = 2*np.abs((x+STEP)%(2*STEP)-STEP)-STEP
        return _ecc_decode(score.reshape(repeats,-1).sum(axis=0))

    def render(self,fmt):
        with TemporaryDirectory() as d:
            src, co, dst = (Path(d)/n for n in ('source.jpg','coef.bin','out.jpg'))
            src.write_bytes(self.data)
            co.write_bytes(self.co.astype('<i2',copy=False).tobytes())
            _run('write',src,co,dst)
            if dst.stat().st_size>MAX_FILE: raise ImageError('JPEG result exceeds file limit.')
            return dst.read_bytes()


def _rng(seed):
    return np.random.PCG64(int.from_bytes(hashlib.sha256(seed).digest()[:16],'big'))

def _rank(seed, population, take=None):
    keys = _rng(seed).random_raw(population)
    return np.argsort(keys,kind='stable')[:take].astype(np.int32,copy=False)


def _make_codebook():
    nibbles = np.arange(16,dtype=np.uint8)[:,None]
    a,b,c,d = ((nibbles >> np.array([3,2,1,0],np.uint8))&1).T
    base = np.stack([a^b^d,a^c^d,a,b^c^d,b,c,d],axis=1)
    return np.concatenate([base,(base.sum(axis=1,keepdims=True)%2).astype(np.uint8)],axis=1)

_CODES = _make_codebook()
_SIGNS = _CODES.astype(np.int16)*2-1


def _ecc_encode(data):
    x = np.frombuffer(data,dtype=np.uint8)
    return _CODES[np.stack((x>>4,x&15),axis=1)].reshape(-1)


def _ecc_decode(scores):
    decoded = np.argmax(scores.astype(np.int16).reshape(-1,8) @ _SIGNS.T,axis=1).astype(np.uint8)
    return ((decoded[::2]<<4)|decoded[1::2]).tobytes()

# PNG / BMP Algorithm
# Scores 8x8 tiles by texture & keeps most textured half
# Score ignores last bit -> changing it doesn't change which tiles extraction picks 
# write() hides 3 message bits in 7 RGB channel values flipping at most one last bit 
class _Spatial:
    ident = 1
    name = 'texture-adaptive-matrix'
    def __init__(self,im):
        self.im = im
        a = np.array(im)
        h,w,c = a.shape
        gray = (a[:,:,0]>>1).astype(np.int16) + 2*(a[:,:,1]>>1) + (a[:,:,2]>>1)
        tx,ty = (w+7)//8,(h+7)//8
        padded = np.pad(gray,((0,ty*8-h),(0,tx*8-w)),mode='edge')
        tiles = padded.reshape(ty,8,tx,8).transpose(0,2,1,3)
        score = np.abs(np.diff(tiles,axis=2)).sum(axis=(2,3),dtype=np.int32)
        score += np.abs(np.diff(tiles,axis=3)).sum(axis=(2,3),dtype=np.int32)
        keep = np.zeros(tx*ty,dtype=bool)
        keep[np.argsort(-score.ravel(),kind='stable')[:(tx*ty+1)//2]] = True
        mask = np.repeat(np.repeat(keep.reshape(ty,tx),8,axis=0),8,axis=1)[:h,:w]
        self.alpha = a[:,:,3].copy() if c == 4 else None
        if self.alpha is not None: mask = mask & (self.alpha>0)
        pixels = np.flatnonzero(mask).astype(np.int32,copy=False)
        self.rgb = np.ascontiguousarray(a[:,:,:3]).reshape(-1)
        self.indices = (pixels[:,None]*3+np.arange(3,dtype=np.int32)).reshape(-1)
        self.groups = len(self.indices)//7
        self.hg = (HEADER_BYTES*8+2)//3
        self.order = _rank(b'spatial-public-header-v1'+struct.pack('>II',w,h),self.groups)
        self.shape = h,w

    def fit(self,n): return self.groups >= self.hg + (n*8+2)//3
    def max_body(self): return max(0,(self.groups-self.hg)*3//8)

    def _indices(self,n,seed,header):
        k=(n*8+2)//3
        if header:
            groups=self.order[:k]
        else:
            rest=self.order[self.hg:]
            groups=rest[_rank(seed+b'/spatial/route',len(rest),k)]
        return self.indices[groups[:,None]*7+np.arange(7,dtype=np.int32)]

    def _syndrome(self, indices):
        return np.bitwise_xor.reduce((self.rgb[indices]&1)*np.arange(1,8,dtype=np.uint8),axis=1)

    def write(self,data,seed,header=False):
        idx=self._indices(len(data),seed,header)
        bits=np.unpackbits(np.frombuffer(data,dtype=np.uint8))
        bits=np.pad(bits,(0,(-len(bits))%3)).reshape(-1,3)
        goal=bits @ np.array([4,2,1],np.uint8)
        change=self._syndrome(idx)^goal
        rows=np.flatnonzero(change)
        self.rgb[idx[rows,change[rows]-1]] ^= 1

    def read(self,n,seed,header=False):
        words=self._syndrome(self._indices(n,seed,header))
        bits=((words[:,None]>>np.array([2,1,0],np.uint8))&1).reshape(-1)
        return np.packbits(bits[:n*8]).tobytes()

    def render(self,fmt):
        rgb=Image.fromarray(self.rgb.reshape(*self.shape,3))
        if self.alpha is not None and fmt=='PNG': rgb.putalpha(Image.fromarray(self.alpha))
        return _save(rgb,fmt,**(_icc(self.im) if fmt == 'PNG' else {}))

# Picks the algorithm based on the output 
def _prepare(cover, output_format):
    fmt = _output(output_format)
    im,original,orientation = _load(cover)
    if fmt != 'PNG' and im.mode=='RGBA' and im.getchannel('A').getextrema() != (255,255):
        raise ImageError('This image has transparency. Choose PNG to preserve it.')
    if fmt != 'JPEG': return _Spatial(im),fmt,original,im.size,False
    if original=='JPEG' and orientation==1:
        try:
            codec = _Jpeg(cover)
        except ImageError:
            codec = None
        if codec is not None and int(codec.q.max()) <= STEP//3:
            return codec,fmt,original,im.size,False
    rgb = im.convert('RGB')
    base = _save(rgb,'JPEG',quality=95,subsampling=0,**_icc(im))
    return _Jpeg(base),fmt,original,im.size,True


def _password(password):
    if password is None: return None
    if not isinstance(password,str) or not password:
        raise PasswordError('Provide a nonempty password, or None for an unencrypted demo.')
    try: data = password.encode('utf-8')
    except UnicodeError as exc: raise PasswordError('Invalid password encoding.') from exc
    if len(data)>1024: raise PasswordError('Password exceeds 1024 UTF-8 bytes.')
    return data

# Uses password and random salt -> key for encryption and route to put payload 
def _keys(password, salt):
    if password is None: return None,b'public-demo/'+salt
    key = hashlib.scrypt(password,salt=salt,n=2**15,r=8,p=1,dklen=64,maxmem=64*1024*1024)
    return key[:32],key[32:]


def _crc(data): return struct.pack('>I',zlib.crc32(data))
_HSEED = b'ILAB/public/bootstrap/v1'

# how many message bytes fit after accounting for overhead.measure()
# compares original and modified RGB values and reports distortion 
def capacity(cover: bytes, output_format: str = 'PNG', *, encrypted: bool = True) -> Capacity:
    """Report usable user bytes after header, integrity and error-correction overhead."""
    codec,fmt,original,(w,h),normalized = _prepare(cover,output_format)
    overhead = 16 if encrypted else 4
    return Capacity(original,fmt,codec.name,w,h,min(MAX_MSG,max(0,codec.max_body()-overhead)),
                    encrypted,codec.fit(overhead),normalized)

# Main hiding function 
# Converting text to UTF-8 bytes, checks that it fits, and builds a header
# Header includes message length and whether encrypted or not  
def embed(cover: bytes, message: bytes | str, *, password: str | None = None,
          output_format: str = 'PNG') -> EmbedResult:
    """Embed a binary or UTF-8 message and verify extraction from the exact output."""
    secret = _password(password)
    if isinstance(message,str):
        try: message=message.encode('utf-8')
        except UnicodeError as exc: raise PayloadError('Message is not valid UTF-8.') from exc
    if not isinstance(message,bytes): raise PayloadError('Use bytes or a UTF-8 string.')
    if len(message)>MAX_MSG: raise CapacityError('Payload exceeds the 2 MiB safety limit.')
    codec,fmt,_,_,normalized = _prepare(cover,output_format)
    encrypted = secret is not None
    overhead = 16 if encrypted else 4
    allowed = min(MAX_MSG,max(0,codec.max_body()-overhead))
    if not codec.fit(overhead+len(message)):
        raise CapacityError(f'{len(message)} payload bytes do not fit; usable capacity is {allowed} bytes. Try a larger image or PNG.')
    salt = os.urandom(16)
    nonce = os.urandom(12) if encrypted else bytes(12)
    header = _HEADER.pack(MAGIC,VERSION,codec.ident,encrypted,len(message),salt,nonce)
    header += _crc(header)
    key,route = _keys(secret,salt)
    body = AESGCM(key).encrypt(nonce,message,header) if encrypted else message+_crc(header+message)
    # Hides header & payload
    codec.write(header,_HSEED,header=True)
    codec.write(body,route)
    rendered = codec.render(fmt)
    # tries extracting from the finished image to make sure it got the right message (matches) at that the new image works
    try:
        recovered = _extract(rendered,secret,prederived=(salt,key,route))
    except StegoError as exc:
        raise PayloadError('The generated image did not pass the extraction check; no file was returned.') from exc
    if recovered != message: raise PayloadError('The generated image failed byte-for-byte verification.')
    return EmbedResult(rendered,fmt,{'PNG':'image/png','BMP':'image/bmp','JPEG':'image/jpeg'}[fmt],
                       codec.name,len(message),allowed,normalized)

# reads the header, before needing the password
# checks that header belongs to our app, and learns how much to read 
# w/ same password and salt -> recreates route and encryption key 
def _extract(stego, secret, prederived=None):
    im,fmt,_ = _load(stego)
    if fmt not in ('PNG','BMP','JPEG'):
        raise ImageError('Extract from the generated PNG, BMP or JPEG, not the source HEIC.')
    codec = _Jpeg(stego) if fmt=='JPEG' else _Spatial(im)
    if not codec.fit(0): raise PayloadError('Image is too small to contain a compatible message.')
    header = codec.read(HEADER_BYTES,_HSEED,header=True)
    raw, check = header[:-4], header[-4:]
    magic,version,ident,flag,length,salt,nonce = _HEADER.unpack(raw)
    if magic!=MAGIC or _crc(raw)!=check:
        raise PayloadError('No readable Image Stego Lab payload; the file may be unsupported or altered.')
    if version!=VERSION or ident!=codec.ident or flag not in (0,1):
        raise PayloadError('Unsupported payload version or mode.')
    body_n = length+(16 if flag else 4)
    if length>MAX_MSG or not codec.fit(body_n): raise PayloadError('Inconsistent payload length.')
    if flag and secret is None: raise PasswordError('This message needs its password.')
    secret = secret if flag else None
    if prederived is not None and prederived[0]==salt:
        _,key,route = prederived
    else:
        key,route = _keys(secret,salt)
    body = codec.read(body_n,route)
    if flag:
        try: return AESGCM(key).decrypt(nonce,body,header)
        except InvalidTag as exc: raise PasswordError('Wrong password or image damaged; authentication failed.') from exc
    if _crc(header+body[:-4])!=body[-4:]: raise PayloadError('Hidden message is damaged.')
    return body[:-4]
# if authentication fails -> gives error 

def extract(stego: bytes, *, password: str | None = None) -> bytes:
    """Extract without the original image; never return a failed authentication."""
    return _extract(stego,_password(password))


def measure(cover: bytes, stego: bytes) -> Quality:
    """Compare decoded RGB values; this does not measure detectability."""
    a,_,_ = _load(cover)
    b,_,_ = _load(stego)
    if a.size!=b.size: raise ImageError('Quality measurement requires matching dimensions.')
    h,w = a.height,a.width
    x,y = np.asarray(a)[:,:,:3],np.asarray(b)[:,:,:3]
    sse,changed = 0,0
    for start in range(0,h,128):
        diff = x[start:start+128].astype(np.int16)-y[start:start+128]
        count = np.count_nonzero(diff)
        changed+=int(count)
        sse+=int(np.square(diff,dtype=np.int32).sum(dtype=np.int64))
    mse=sse/(h*w*3)
    return Quality(mse,None if mse==0 else 10*math.log10(255**2/mse),changed/(h*w*3),w,h)


def _bounded_file(path, limit):
    with Path(path).expanduser().open('rb') as stream:
        data=stream.read(limit+1)
    if len(data)>limit: raise StegoError(f'Input exceeds the {limit}-byte limit.')
    return data

# Terminal Interface 
def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    cmd=sub.add_parser('embed',help='Hide text or a file; password requested unless --demo.')
    cmd.add_argument('cover'); cmd.add_argument('output')
    src=cmd.add_mutually_exclusive_group(required=True)
    src.add_argument('--text'); src.add_argument('--file')
    cmd.add_argument('--demo',action='store_true',help='No password; no confidentiality.')
    cmd=sub.add_parser('extract',help='Recover message bytes; prompts if needed.')
    cmd.add_argument('stego'); cmd.add_argument('output')
    cmd=sub.add_parser('capacity'); cmd.add_argument('cover'); cmd.add_argument('--format',default='PNG')
    cmd.add_argument('--demo',action='store_true')
    cmd=sub.add_parser('quality'); cmd.add_argument('cover'); cmd.add_argument('stego')
    args=parser.parse_args(argv)
    try:
        if args.command=='embed':
            fmt={'.png':'PNG','.bmp':'BMP','.jpg':'JPEG','.jpeg':'JPEG'}.get(Path(args.output).suffix.lower())
            if fmt is None: raise ImageError('Output filename must end in .png, .bmp, .jpg or .jpeg.')
            message=args.text if args.file is None else _bounded_file(args.file,MAX_MSG)
            password=None if args.demo else getpass('New password: ')
            result=embed(_bounded_file(args.cover,MAX_FILE),message,password=password,output_format=fmt)
            # Saving the new photo
            with Path(args.output).expanduser().open('xb') as f: f.write(result.image)
            print(f'{result.message_bytes} bytes embedded and verified; mode: {result.mode}.')
        elif args.command=='extract':
            data=_bounded_file(args.stego,MAX_FILE)
            try: message=extract(data)
            except PasswordError: message=extract(data,password=getpass('Password: '))
            # Saving the recovered text 
            with Path(args.output).expanduser().open('xb') as f: f.write(message) # xb = create new binary file, don't overwrite
            print(f'{len(message)} bytes recovered.')
        elif args.command=='capacity':
            print(json.dumps(asdict(capacity(_bounded_file(args.cover,MAX_FILE),args.format,encrypted=not args.demo)),indent=2))
        else:
            print(json.dumps(asdict(measure(_bounded_file(args.cover,MAX_FILE),_bounded_file(args.stego,MAX_FILE))),indent=2))
    except (StegoError,OSError,EOFError) as exc:
        parser.exit(2,f'Error: {exc}\n')

if __name__=='__main__': main()
