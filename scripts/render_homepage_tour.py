from PIL import Image,ImageDraw,ImageFont
from pathlib import Path
import subprocess
import tempfile
temporary = tempfile.TemporaryDirectory(prefix='proofpage-tour-')
root = Path(temporary.name)
font='/System/Library/Fonts/Supplemental/Arial.ttf'
scenes=[('library.png','Keep a source you can return to.','Pages, revisions and review status in one local library.'),('library.png','The source stays with the work.','Inspect captured evidence before using it in research or training.'),('claim-check.png','Check the words. Keep the context.','Compare quotes against saved passages. A match is not a truth verdict.')]
for n,(src,title,caption) in enumerate(scenes):
 im=Image.new('RGB',(1280,720),'#101411');d=ImageDraw.Draw(im)
 d.text((48,26),'Proofpage',font=ImageFont.truetype(font,22),fill='#c8e7a7')
 d.text((48,68),title,font=ImageFont.truetype(font,32),fill='#f0eee5')
 d.text((48,114),caption,font=ImageFont.truetype(font,17),fill='#b0b9ad')
 shot=Image.open('website/images/'+src).convert('RGB');shot.thumbnail((1120,540))
 im.paste(shot,((1280-shot.width)//2,163))
 im.save(root/f'{n}.png')
 subprocess.run(['ffmpeg','-y','-loop','1','-i',str(root/f'{n}.png'),'-vf',"zoompan=z='min(zoom+0.00012,1.025)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=150:s=1280x720:fps=25,fade=t=in:st=0:d=0.35,fade=t=out:st=5.6:d=0.4",'-t','6','-c:v','libx264','-preset','fast','-crf','23','-pix_fmt','yuv420p',str(root/f'{n}.mp4')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
(root/'concat.txt').write_text(''.join(f"file '{root}/{n}.mp4'\n" for n in range(3)))
subprocess.run(['ffmpeg','-y','-f','concat','-safe','0','-i',str(root/'concat.txt'),'-c','copy','-movflags','+faststart','website/videos/proofpage-tour.mp4'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
Image.open(root/'0.png').save('website/images/tour-poster.jpg',quality=88)
