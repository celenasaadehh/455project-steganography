#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <setjmp.h>
#include <jpeglib.h>
struct err { struct jpeg_error_mgr pub; jmp_buf *jmp; };
static void fail(j_common_ptr c) {
    struct err *e = (struct err *) c->err;
    (*c->err->output_message)(c); longjmp(*e->jmp, 1);
}
static void warning(j_common_ptr c, int level) { if(level < 0) fail(c); }
static void u32(FILE *f, unsigned int v) { for(int i=0;i<4;i++) fputc((v>>(8*i))&255, f); }
static const int freq[] = { 10,17,11,25 };
int main(int argc, char **argv) {
    int write = argc == 5 && strcmp(argv[1],"write")==0;
    if (!write && !(argc == 4 && strcmp(argv[1],"read")==0)) return 2;
    FILE *in=fopen(argv[2],"rb"), *data=fopen(argv[3],write?"rb":"wb");
    if (!in || !data) return 2;
    struct jpeg_decompress_struct src;
    struct jpeg_compress_struct dst;
    struct err es, ed; jmp_buf jb;
    if (setjmp(jb)) return 3;
    src.err=jpeg_std_error(&es.pub); es.jmp=&jb; es.pub.error_exit=fail; es.pub.emit_message=warning;
    jpeg_create_decompress(&src); jpeg_stdio_src(&src,in);
    jpeg_save_markers(&src, JPEG_APP0+2, 0xffff);
    jpeg_read_header(&src,TRUE);
    if(src.data_precision!=8 || (src.jpeg_color_space!=JCS_GRAYSCALE && src.jpeg_color_space!=JCS_YCbCr)
        || (uint64_t)src.image_width*src.image_height>25000000) return 4;
    jvirt_barray_ptr *a=jpeg_read_coefficients(&src);
    if(src.comp_info[0].h_samp_factor!=src.max_h_samp_factor || src.comp_info[0].v_samp_factor!=src.max_v_samp_factor) return 4;
    unsigned int h=src.image_height/8, w=src.image_width/8;
    JQUANT_TBL *q=src.comp_info[0].quant_table;
    if(!q || w>src.comp_info[0].width_in_blocks || h>src.comp_info[0].height_in_blocks) return 4;
    if(!write) {
        u32(data,w); u32(data,h); for(int k=0;k<4;k++) u32(data,q->quantval[freq[k]]);
    }
    for(unsigned int y=0;y<h;y++) {
        JBLOCKARRAY row=(*src.mem->access_virt_barray)((j_common_ptr)&src,a[0],y,1,write);
        for(unsigned int x=0;x<w;x++) for(int k=0;k<4;k++) {
            JCOEF *p=&row[0][x][freq[k]];
            if(write) {
                int lo=fgetc(data), hi=fgetc(data);
                if(lo==EOF || hi==EOF) return 2;
                int v=lo + 256*hi;
                *p=(JCOEF)(v>=32768?v-65536:v);
            } else {
                unsigned int v=(uint16_t)*p; fputc(v&255,data); fputc(v>>8,data);
            }
        }
    }
    if(write) {
        if(fgetc(data)!=EOF || ferror(data)) return 2;
        FILE *out=fopen(argv[4],"wb"); if(!out) return 2;
        dst.err=jpeg_std_error(&ed.pub); ed.jmp=&jb; ed.pub.error_exit=fail; ed.pub.emit_message=warning;
        jpeg_create_compress(&dst); jpeg_stdio_dest(&dst,out);
        jpeg_copy_critical_parameters(&src,&dst); dst.optimize_coding=TRUE;
        jpeg_write_coefficients(&dst,a);
        for(jpeg_saved_marker_ptr m=src.marker_list;m;m=m->next)
            if(m->marker==JPEG_APP0+2 && m->data_length>=14 && !memcmp(m->data,"ICC_PROFILE\0",12))
                jpeg_write_marker(&dst,m->marker,m->data,m->data_length);
        jpeg_finish_compress(&dst); jpeg_destroy_compress(&dst);
        if(fclose(out)) return 2;
    }
    jpeg_finish_decompress(&src); jpeg_destroy_decompress(&src);
    fclose(in); return fclose(data)?2:0;
}
