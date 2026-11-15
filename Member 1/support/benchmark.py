"""Reproduce the small cross-cover benchmark (see README)."""
import argparse,csv,hashlib
from io import BytesIO
from pathlib import Path
import numpy as np
from PIL import Image
from skimage import data
from skimage.metrics import structural_similarity
import image_stego as s

def encode(im, fmt='JPEG', **kw):
    out=BytesIO(); im.save(out,fmt,**kw); return out.getvalue()

def assess(candidate, expected):
    try: return int(s.extract(candidate)==expected)
    except s.StegoError: return 0

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',default='results.csv'); args=p.parse_args()
    rows=[]
    for name in ('astronaut','coffee','chelsea','rocket','camera','text','checkerboard'):
        im=Image.fromarray(getattr(data,name)()).convert('RGB')
        if min(im.size)<300: im=im.resize((max(512,im.width),max(384,im.height)),Image.Resampling.NEAREST)
        cover=encode(im,quality=95,subsampling=0)
        ping=encode(im,'PNG')
        for n in (24,96,160):
            msg=hashlib.shake_256(f'{name}/{n}'.encode()).digest(n)
            jpeg=s.embed(cover,msg,output_format='JPEG')
            png=s.embed(ping,msg,output_format='PNG')
            qim=s.measure(cover,jpeg.image)
            raw=Image.open(BytesIO(jpeg.image)); original=Image.open(BytesIO(cover))
            spatial=s.measure(ping,png.image)
            rng=np.random.default_rng(123)
            base=np.array(im); pix=base.reshape(-1)
            bits=rng.integers(0,2,(s.HEADER_BYTES+n+4)*8,dtype=np.uint8)
            pix[:len(bits)]=(pix[:len(bits)]&254)|bits
            baseline=s.measure(ping,encode(Image.fromarray(base),'PNG'))
            vals={f'q{q}':assess(encode(raw,quality=q,subsampling=2),msg) for q in (95,90,85,75,60,50,40,30,20)}
            resized=raw.resize((raw.width*3//4,raw.height*3//4),Image.Resampling.LANCZOS)
            rows.append(dict(cover=name,payload_bytes=n,jpeg_capacity=jpeg.capacity_bytes,png_capacity=png.capacity_bytes,
                jpeg_psnr=round(qim.psnr_db,3),jpeg_ssim=round(structural_similarity(np.asarray(original),np.asarray(raw),channel_axis=2,data_range=255),5),
                png_psnr=round(spatial.psnr_db,3),basic_lsb_psnr=round(baseline.psnr_db,3),
                exact=assess(jpeg.image,msg),png_exact=assess(png.image,msg),png_resave=assess(encode(Image.open(BytesIO(png.image)),'PNG',compress_level=9),msg),
                png_as_jpeg=assess(encode(Image.open(BytesIO(png.image)),quality=95),msg),jpeg_resize=assess(encode(resized,quality=90),msg),**vals))
    with Path(args.out).open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    for k in ('exact','png_exact','png_resave','png_as_jpeg','jpeg_resize','q95','q90','q85','q75','q60','q50','q40','q30','q20'):
        print(k,sum(row[k] for row in rows),'/',len(rows))

if __name__=='__main__': main()
