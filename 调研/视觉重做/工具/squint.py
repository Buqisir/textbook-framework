import sys
from PIL import Image, ImageFilter, ImageOps
d=sys.argv[1]
def spread(a,b,out,blur=0):
    A=Image.open(f"{d}/p-{a}.png"); B=Image.open(f"{d}/p-{b}.png")
    S=Image.new("RGB",(A.width+B.width+8,A.height),"#999"); S.paste(A,(0,0)); S.paste(B,(A.width+8,0))
    if blur: S=ImageOps.grayscale(S).filter(ImageFilter.GaussianBlur(blur))
    S.save(f"{d}/{out}")
spread(2,3,"对页-2-3.png"); spread(2,3,"眯眼-2-3.png",blur=6)
spread(4,5,"对页-4-5.png"); spread(4,5,"眯眼-4-5.png",blur=6)
