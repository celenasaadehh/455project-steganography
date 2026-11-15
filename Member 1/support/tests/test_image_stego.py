import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import image_stego as s


def make_image(w=512,h=384):
    y,x=np.indices((h,w))
    values=np.stack([(x+2*y)%240+8,(x//2+2*y)%235+10,(x+3*y)%233+11],axis=-1)
    return Image.fromarray(values.astype(np.uint8))


def save(im,fmt,**kw):
    b=BytesIO(); im.save(b,fmt,**kw); return b.getvalue()


class ImageStegoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.im=make_image()
        cls.png=save(cls.im,'PNG')
        cls.jpg=save(cls.im,'JPEG',quality=95,subsampling=0)

    def test_png_unicode_encrypted(self):
        text='مرحباً — image lab 🔍'
        stego=s.embed(self.png,text,password='course demo passphrase')
        self.assertEqual(s.extract(stego.image,password='course demo passphrase'),text.encode())
        self.assertEqual(stego.media_type,'image/png')
        with self.assertRaises(s.PasswordError): s.extract(stego.image)
        with self.assertRaises(s.PasswordError): s.extract(stego.image,password='incorrect')

    def test_bmp_roundtrip_and_png_bmp_lossless_conversion(self):
        data=b'\x00\xffbinary\x80\x00'
        original=save(self.im,'BMP')
        b=s.embed(original,data,output_format='BMP')
        self.assertEqual(s.extract(b.image),data)
        self.assertEqual(s.extract(save(Image.open(BytesIO(b.image)),'PNG')),data)

    def test_png_alpha_and_no_hidden_rgb_changes_behind_zero_alpha(self):
        rgba=np.array(self.im.convert('RGBA')); rgba[:100,:,3]=0; rgba[100:150,:,3]=128
        src=save(Image.fromarray(rgba),'PNG')
        r=s.embed(src,b'alpha preserved')
        out=np.array(Image.open(BytesIO(r.image)))
        self.assertTrue(np.array_equal(out[:,:,3],rgba[:,:,3]))
        self.assertTrue(np.array_equal(out[:100],rgba[:100]))
        self.assertEqual(s.extract(r.image),b'alpha preserved')
        for fmt in ('BMP','JPEG'):
            with self.assertRaises(s.ImageError): s.embed(src,b'test',output_format=fmt)

    def test_exact_spatial_capacity(self):
        c=s.capacity(self.png,encrypted=True)
        self.assertTrue(c.can_embed)
        data=b'A'*c.max_message_bytes
        r=s.embed(self.png,data,password='max-pass')
        self.assertEqual(s.extract(r.image,password='max-pass'),data)
        with self.assertRaises(s.CapacityError): s.embed(self.png,data+b'a',password='max-pass')

    def test_empty_message(self):
        self.assertEqual(s.extract(s.embed(self.png,b'').image),b'')

    def test_clean_and_tiny_inputs_are_not_payloads(self):
        with self.assertRaises(s.PayloadError): s.extract(self.png)
        tiny=save(Image.new('RGB',(3,3)),'PNG')
        self.assertFalse(s.capacity(tiny).can_embed)
        with self.assertRaises(s.CapacityError): s.embed(tiny,b'')
        with self.assertRaises(s.PayloadError): s.extract(tiny)

    def test_bad_images_and_unsupported_formats(self):
        for raw in (b'invalid',save(self.im,'GIF'),b''):
            with self.subTest(raw=raw[:10]), self.assertRaises(s.ImageError): s.embed(raw,b'a')
        with self.assertRaises(s.ImageError): s.embed(self.png,b'a',output_format='HEIC')
        with self.assertRaises(s.PasswordError): s.embed(self.png,b'a',password='')

    def test_plain_body_corruption_is_rejected(self):
        out=s.embed(self.png,b'integrity')
        im,_,_=s._load(out.image)
        codec=s._Spatial(im)
        header=codec.read(s.HEADER_BYTES,s._HSEED,header=True)
        *_,salt,_=s._HEADER.unpack(header[:-4])
        _,seed=s._keys(None,salt)
        idx=codec._indices(len(b'integrity')+4,seed,False)
        codec.rgb[idx[0,0]] ^= 1
        with self.assertRaises(s.PayloadError): s.extract(codec.render('PNG'))

    def test_jpeg_dct_encryption_and_recompression(self):
        data=b'\x00\xff'*48
        r=s.embed(self.jpg,data,password='jpeg-pass',output_format='JPEG')
        self.assertEqual(r.mode,'jpeg-dct-qim-ecc')
        self.assertFalse(r.jpeg_normalized)
        self.assertTrue(r.image.startswith(b'\xff\xd8'))
        self.assertEqual(s.extract(r.image,password='jpeg-pass'),data)
        before,after=s._Jpeg(self.jpg),s._Jpeg(r.image)
        self.assertTrue(np.array_equal(before.q,after.q))
        self.assertTrue(np.any(before.co!=after.co))
        for q in (95,85,75,60):
            with self.subTest(quality=q):
                recompressed=save(Image.open(BytesIO(r.image)),'JPEG',quality=q,subsampling=2)
                self.assertEqual(s.extract(recompressed,password='jpeg-pass'),data)
        with self.assertRaises(s.PasswordError): s.extract(r.image,password='wrong')

    def test_jpeg_normalization_and_odd_dimensions(self):
        odd=save(make_image(517,389),'PNG')
        r=s.embed(odd,b'from PNG',output_format='JPEG')
        self.assertTrue(r.jpeg_normalized)
        self.assertEqual(Image.open(BytesIO(r.image)).size,(517,389))
        self.assertEqual(s.extract(r.image),b'from PNG')
        low=save(self.im,'JPEG',quality=25)
        m=s.embed(low,b'from low JPEG',output_format='JPEG')
        self.assertTrue(m.jpeg_normalized)
        self.assertEqual(s.extract(m.image),b'from low JPEG')

    def test_progressive_grayscale_jpeg(self):
        gray=save(self.im.convert('L'),'JPEG',quality=95,progressive=True)
        r=s.embed(gray,b'grayscale',output_format='JPEG')
        self.assertEqual(s.extract(r.image),b'grayscale')
        self.assertEqual(Image.open(BytesIO(r.image)).mode,'L')

    def test_jpeg_capacity_is_exact(self):
        cap=s.capacity(self.jpg,output_format='JPEG',encrypted=False)
        data=b'#'*cap.max_message_bytes
        self.assertEqual(s.extract(s.embed(self.jpg,data,output_format='JPEG').image),data)
        with self.assertRaises(s.CapacityError): s.embed(self.jpg,data+b'#',output_format='JPEG')

    def test_metadata_independence_and_orientation(self):
        exif=Image.Exif(); exif[274]=6; exif[315]='Do not retain artist metadata'
        cover=save(self.im,'JPEG',quality=95,exif=exif)
        r=s.embed(cover,b'normalised orientation',output_format='JPEG')
        with Image.open(BytesIO(r.image)) as decoded:
            self.assertEqual(decoded.size,self.im.size[::-1]); self.assertNotIn(315,decoded.getexif())
        self.assertEqual(s.extract(r.image),b'normalised orientation')
        self.assertEqual(s.measure(cover,r.image).width,self.im.height)

    def test_one_bit_per_ecc_word(self):
        msg=bytes(range(256)); e=s._ecc_encode(msg).astype(np.int16)*2-1
        e.reshape(-1,8)[:,2]*=-1
        self.assertEqual(s._ecc_decode(e),msg)

    def test_missing_jpeg_helper_never_falls_back_to_pixel_jpeg(self):
        with patch.dict('os.environ',{'STEGO_JPEG_TOOL':'missing/jpegtool'}):
            with self.assertRaises(s.DependencyError): s.embed(self.png,b'a',output_format='JPEG')

    def test_real_heic_can_be_used_as_cover_for_png_and_jpeg(self):
        heic = (Path(__file__).parent/'fixtures'/'synthetic.heic').read_bytes()
        try:
            a = s.capacity(heic,encrypted=False)
        except s.DependencyError as exc:
            self.skipTest(str(exc))
        self.assertEqual(a.input_format,'HEIF')
        for fmt in ('PNG','JPEG'):
            with self.subTest(format=fmt):
                r=s.embed(heic,b'HEIC input',output_format=fmt)
                self.assertEqual(s.extract(r.image),b'HEIC input')

    def test_quality_values(self):
        q=s.measure(self.png,self.png)
        self.assertIsNone(q.psnr_db)
        self.assertEqual(q.mse,0)
        self.assertGreater(s.measure(self.png,s.embed(self.png,b'x').image).psnr_db,60)


if __name__=='__main__': unittest.main()
