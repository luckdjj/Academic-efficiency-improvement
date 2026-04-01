# -*- coding: utf-8 -*-
import json, sys, io, hashlib
from pathlib import Path
from datetime import datetime
from PIL import Image

def extract_images_from_pdf(pdf_path, pdf_index):
    import fitz
    images = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        print(f"      [错误] 无法打开: {e}")
        return [], {}
    page_count = len(doc)
    title = ""
    if page_count > 0:
        try:
            title = doc[0].get_text("text").strip().split("\n")[0][:80]
        except Exception:
            title = ""
    img_id = 0
    for page_num in range(page_count):
        page = doc[page_num]
        try:
            img_list = page.get_images(full=True)
        except Exception:
            continue
        for img_info in img_list:
            img_id += 1
            try:
                xref = img_info[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                ext = base_image["ext"]
                pil_img = Image.open(io.BytesIO(img_bytes))
                width, height = pil_img.size
                area = width * height
                if area < 2500:
                    continue
                size_cat = "large" if area > 500000 else "medium" if area > 100000 else "small"
                safe_ext = ext.lower() if ext.lower() in ("jpeg","jpg","png","gif","bmp","webp") else "png"
                filename = f"p{pdf_index:02d}_{img_id:03d}_{width}x{height}.{safe_ext}"
                images.append({
                    "id": img_id, "filename": filename,
                    "pdf_index": pdf_index, "pdf_name": pdf_path.name,
                    "pdf_page": page_num + 1, "pdf_total_pages": page_count,
                    "image_index": img_id, "width": width, "height": height,
                    "area": area, "size_category": size_cat,
                    "file_size_kb": len(img_bytes) / 1024,
                    "format": ext, "_xref": xref,
                })
            except Exception:
                pass
    doc.close()
    return images, {"title": title, "page_count": page_count}

class GalleryUpdater:
    def __init__(self, config):
        self.name = config["name"]
        self.pdf_dir = Path(config["pdf_dir"])
        self.output_dir = Path(config["output_dir"])
        self.extracted_dir = self.output_dir / "extracted_images"
        self.analysis_dir = self.output_dir / "image_analysis"
        self.extracted_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.analysis_dir / "gallery_state.json"
        self.meta_file = self.analysis_dir / "image_metadata.json"
        self.pdf_ref_file = self.analysis_dir / "pdf_refs.json"
        self._state = None

    def _load_state(self):
        if self.state_file.exists():
            with open(self.state_file, "r", encoding="utf-8") as f:
                self._state = json.load(f)
        else:
            self._state = {"last_update": None, "pdf_hashes": {}, "image_count": 0, "total_size_mb": 0.0}

    def _save_state(self):
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    def _hash(self, path):
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    def _check_changes(self):
        pdfs = sorted(self.pdf_dir.glob("*.pdf"))
        current = {p.name: self._hash(p) for p in pdfs}
        old = self._state.get("pdf_hashes", {})
        added   = [n for n in current if n not in old]
        removed = [n for n in old   if n not in current]
        changed = [n for n in current if n in old and current[n] != old[n]]
        if not (added or removed or changed):
            return {"changed": False, "added": [], "removed": [], "modified": []}
        return {"changed": True, "added": added, "removed": removed, "modified": changed}

    def _extract_all(self):
        import fitz
        pdfs = sorted(self.pdf_dir.glob("*.pdf"))
        all_images = []
        all_pdf_refs = []
        total_size_kb = 0
        for i, pdf_path in enumerate(pdfs, 1):
            print(f"    [{i}/{len(pdfs)}] {pdf_path.name[:55]}")
            imgs, ref = extract_images_from_pdf(pdf_path, i)
            for img in imgs:
                out_path = self.extracted_dir / img["filename"]
                try:
                    doc = fitz.open(str(pdf_path))
                    base_image = doc.extract_image(img["_xref"])
                    img_bytes = base_image["image"]
                    doc.close()
                except Exception:
                    continue
                with open(out_path, "wb") as f:
                    f.write(img_bytes)
                img["file_size_kb"] = len(img_bytes) / 1024
                total_size_kb += img["file_size_kb"]
                img.pop("_xref", None)
                all_images.append(img)
            all_pdf_refs.append({
                "index": i, "name": pdf_path.name, "path": str(pdf_path),
                "title": ref.get("title", ""), "page_count": ref.get("page_count", 0),
                "image_count": len(imgs),
            })
            cnt = f"      -> {len(imgs)} 张" if imgs else "      -> 无图片"
            print(cnt)
        return all_images, all_pdf_refs, total_size_kb

    def _generate_html(self, images, pdf_refs):
        import fitz
        img_count = len(images)
        pdf_count = len(pdf_refs)
        total_mb = sum(i["file_size_kb"] for i in images) / 1024
        update_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        safe_images = [{k: v for k, v in img.items() if k != "_xref"} for img in images]
        data_json = json.dumps(safe_images, ensure_ascii=False)
        out_dir_json = json.dumps(str(self.output_dir))
        size_label = {"large": "大", "medium": "中", "small": "小"}

        JS = """
const DATA = __DATA__;
const OUT_DIR = __OUT_DIR__;
let cur = [...DATA];

function render(){
  var g=document.getElementById("gallery");
  if(!cur.length){
    g.innerHTML='<div style="text-align:center;padding:60px;color:#999">未找到匹配图片</div>';
    document.getElementById("resultTip").innerText="";return;
  }
  document.getElementById("resultTip").innerText="显示 "+cur.length+" / "+DATA.length+" 张";
  g.innerHTML="";
  cur.forEach(function(img){
    var c=document.createElement("div");c.className="card";
    var sz=img.size_category==="large"?"\u5927":img.size_category==="medium"?"\u4e2d":"\u5c0f";
    c.innerHTML='<div class="preview"><img src="../extracted_images/'+img.filename+'" alt="" onerror="this.src=\'data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 width=%22100%22 height=%22100%22%3E%3Crect fill=%22%23eee%22 width=%22100%22 height=%22100%22/%3E%3Ctext x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22 font-size=%2212%22%3E\u52a0\u8f7d\u5931\u8d25%3C/text%3E%3C/svg%3E\'"></div>'+
'<div class="info"><div class="filename">'+img.filename+'</div>'+
'<div class="source-pdf"><div class="src-label">PDF</div><div class="src-name">'+img.pdf_name+'</div></div>'+
'<div class="meta"><div class="meta-item">\u5c3a\u5bf8: <span>'+img.width+'\u00d7'+img.height+'</span></div>'+
'<div class="meta-item">\u5206\u7c7b: <span>'+sz+'</span></div>'+
'<div class="meta-item">\u5927\u5c0f: <span>'+img.file_size_kb.toFixed(1)+'KB</span></div>'+
'<div class="meta-item">\u9875: <span>'+img.pdf_page+'/'+img.pdf_total_pages+'</span></div></div>'+
'<div class="tags"><span class="tag">PDF#'+img.pdf_index+'</span><span class="tag">\u56fe#'+img.image_index+'</span></div></div>';
    c.addEventListener("click",function(){show(img);});
    g.appendChild(c);
  });
}

var curImg=null;
function show(img){
  curImg=img;
  document.getElementById("modalTitle").innerText=img.filename;
  document.getElementById("modalPdfName").innerText=img.pdf_name;
  document.getElementById("modalPdfInfo").innerText="\u7b2c "+img.pdf_page+" \u9875 / \u5171 "+img.pdf_total_pages+" \u9875 | \u56fe\u7247\u5e8f\u53f7 #"+img.image_index;
  document.getElementById("modalImg").src="../extracted_images/"+img.filename;
  document.getElementById("mFn").innerText=img.filename;
  document.getElementById("mDim").innerText=img.width+" \u00d7 "+img.height+" px";
  document.getElementById("mArea").innerText=img.area.toLocaleString()+" px";
  document.getElementById("mSz").innerText=img.file_size_kb.toFixed(2)+" KB";
  document.getElementById("mFmt").innerText=img.format;
  document.getElementById("mPdf").innerText=img.pdf_name;
  document.getElementById("mPage").innerText="\u7b2c "+img.pdf_page+" \u9875 / \u5171 "+img.pdf_total_pages+" \u9875";
  document.getElementById("mIdx").innerText="#"+img.image_index;
  document.getElementById("modal").style.display="block";
}
function closeM(){document.getElementById("modal").style.display="none";}
function openOrig(){if(curImg)window.open("../extracted_images/"+curImg.filename,"_blank");}
function copyPath(){
  if(!curImg)return;
  var p=OUT_DIR+"\\\\extracted_images\\\\"+curImg.filename;
  navigator.clipboard.writeText(p).then(function(){
    var b=document.createElement("div");
    b.style.cssText="position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:#333;color:#fff;padding:10px 20px;border-radius:8px;font-size:13px;z-index:9999";
    b.innerText="\u8def\u5f84\u5df2\u590d\u5236!";document.body.appendChild(b);setTimeout(function(){b.remove();},2000);
  });
}
document.addEventListener("DOMContentLoaded",function(){
  var btns=document.querySelectorAll(".filter-btn");
  btns.forEach(function(b){
    b.addEventListener("click",function(){
      btns.forEach(function(x){x.classList.remove("active");});
      b.classList.add("active");
      var sz=b.getAttribute("data-size");
      cur=sz==="all"?[].concat(DATA):DATA.filter(function(x){return x.size_category===sz;});
      render();
    });
  });
  document.getElementById("searchBox").addEventListener("input",function(e){
    var q=e.target.value.trim().toLowerCase();
    var act=document.querySelector(".filter-btn.active").getAttribute("data-size");
    if(q){
      cur=DATA.filter(function(x){return x.filename.toLowerCase().indexOf(q)>-1||x.pdf_name.toLowerCase().indexOf(q)>-1;});
    } else {
      cur=act==="all"?[].concat(DATA):DATA.filter(function(x){return x.size_category===act;});
    }
    render();
  });
  render();
});
window.onclick=function(e){if(e.target===document.getElementById("modal"))closeM();}
""".replace("__DATA__", data_json).replace("__OUT_DIR__", out_dir_json)

        html = (
'<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n<meta charset="UTF-8">\n'
'<meta name="viewport" content="width=device-width,initial-scale=1.0">\n'
'<title>' + self.name + ' - \u56fe\u7247\u5e93</title>\n'
'<style>\n'
'*{margin:0;padding:0;box-sizing:border-box}\n'
'body{font-family:\'Segoe UI\',sans-serif;background:#f0f2f5;min-height:100vh}\n'
'.container{max-width:1400px;margin:0 auto;padding:20px}\n'
'header{background:#fff;padding:24px 30px;border-radius:10px;margin-bottom:20px;box-shadow:0 2px 8px rgba(0,0,0,.08)}\n'
'h1{color:#1a1a2e;margin-bottom:6px}\n'
'.subtitle{color:#666;font-size:14px}\n'
'.info-bar{display:flex;flex-wrap:wrap;gap:12px;margin-top:14px}\n'
'.badge{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:8px 16px;border-radius:20px;font-size:13px;text-align:center}\n'
'.badge .num{font-size:20px;font-weight:700;display:block}\n'
'.controls{background:#fff;padding:20px 24px;border-radius:10px;margin-bottom:16px;box-shadow:0 2px 8px rgba(0,0,0,.06);display:flex;flex-wrap:wrap;gap:16px;align-items:center}\n'
'.controls label{font-size:13px;color:#555}\n'
'.search{flex:1;min-width:200px;padding:10px 14px;border:2px solid #e0e0e0;border-radius:8px;font-size:14px}\n'
'.search:focus{outline:none;border-color:#667eea}\n'
'.filter-btn{padding:8px 14px;border:2px solid #ddd;background:#fff;border-radius:8px;cursor:pointer;font-size:13px;transition:.2s}\n'
'.filter-btn:hover{border-color:#667eea;color:#667eea}\n'
'.filter-btn.active{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;border-color:#667eea}\n'
'.gallery{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:18px}\n'
'.card{background:#fff;border-radius:10px;overflow:hidden;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.07);transition:transform .2s,box-shadow .2s}\n'
'.card:hover{transform:translateY(-4px);box-shadow:0 6px 16px rgba(0,0,0,.13)}\n'
'.preview{height:180px;background:#fafafa;display:flex;align-items:center;justify-content:center;overflow:hidden}\n'
'.preview img{width:100%;height:100%;object-fit:cover}\n'
'.info{padding:14px}\n'
'.filename{font-size:11px;color:#999;font-family:monospace;margin-bottom:6px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}\n'
'.source-pdf{background:#eef2ff;border-left:3px solid #667eea;padding:8px 10px;border-radius:4px;margin-bottom:10px}\n'
'.src-label{font-size:10px;color:#667eea;font-weight:700;text-transform:uppercase}\n'
'.src-name{font-size:12px;color:#333;margin-top:3px;word-break:break-word;line-height:1.4}\n'
'.meta{display:grid;grid-template-columns:1fr 1fr;gap:6px}\n'
'.meta-item{background:#f8f9fa;padding:5px 8px;border-radius:4px;font-size:11px;color:#555}\n'
'.meta-item span{color:#222;font-weight:600}\n'
'.tags{display:flex;flex-wrap:wrap;gap:5px;margin-top:8px}\n'
'.tag{background:#e3f2fd;color:#1565c0;padding:2px 8px;border-radius:10px;font-size:10px}\n'
'.modal{display:none;position:fixed;z-index:1000;left:0;top:0;width:100%;height:100%;background:rgba(0,0,0,.75);overflow-y:auto}\n'
'.modal-content{background:#fff;margin:3% auto;width:92%;max-width:960px;border-radius:12px;overflow:hidden;box-shadow:0 8px 32px rgba(0,0,0,.3)}\n'
'.modal-hdr{background:linear-gradient(135deg,#667eea,#764ba2);padding:18px 24px;display:flex;justify-content:space-between;align-items:center}\n'
'.modal-hdr h2{color:#fff;font-size:18px;margin:0}\n'
'.close{background:none;border:none;color:#fff;font-size:30px;cursor:pointer;line-height:1}\n'
'.modal-body{padding:24px}\n'
'.src-hlgt{background:#fffbeb;border-left:4px solid #f59e0b;padding:14px;border-radius:6px;margin-bottom:16px}\n'
'.src-hlgt h4{color:#92400e;font-size:13px;margin-bottom:6px}\n'
'.src-hlgt .pdf-name{color:#92400e;font-size:13px;font-weight:600;word-break:break-word}\n'
'.src-hlgt .pdf-info{color:#92400e;font-size:12px;margin-top:4px}\n'
'.modal-img{width:100%;max-height:480px;object-fit:contain;border-radius:8px;background:#f5f5f5}\n'
'.modal-grid{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-top:16px}\n'
'.modal-sec{background:#f8f9fa;padding:14px;border-radius:8px}\n'
'.modal-sec h3{color:#667eea;font-size:13px;margin-bottom:10px}\n'
'.modal-row{display:flex;gap:8px;margin-bottom:8px;font-size:13px}\n'
'.modal-row .lbl{font-weight:600;color:#333;min-width:80px}\n'
'.modal-row .val{color:#555;word-break:break-word}\n'
'.btns{display:flex;gap:10px;margin-top:16px}\n'
'.btn{flex:1;padding:11px;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600}\n'
'.btn-primary{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff}\n'
'.btn-outline{background:#fff;color:#667eea;border:2px solid #667eea}\n'
'</style>\n'
'</head>\n<body>\n<div class="container">\n<header>\n'
'  <h1>' + self.name + ' &#x1f33e; \u56fe\u7247\u5e93</h1>\n'
'  <p class="subtitle">\u4ece ' + str(pdf_count) + ' \u4e2a PDF \u4e2d\u63d0\u53d6 ' + str(img_count) + ' \u5f20\u56fe\u7247 | \u6700\u540e\u66f4\u65b0: ' + update_time + '</p>\n'
'  <div class="info-bar">\n'
'    <div class="badge"><span class="num">' + str(img_count) + '</span>\u56fe\u7247</div>\n'
'    <div class="badge"><span class="num">' + str(pdf_count) + '</span>PDF</div>\n'
'    <div class="badge"><span class="num">' + ("%.0f" % total_mb) + '</span>MB</div>\n'
'    <div class="badge"><span class="num">' + update_time.split()[0] + '</span>\u66f4\u65b0</div>\n'
'  </div>\n'
'</header>\n'
'<div class="controls">\n'
'  <label>\u7b5b\u9009\uff1a</label>\n'
'  <button class="filter-btn active" data-size="all">\u5168\u90e8</button>\n'
'  <button class="filter-btn" data-size="small">\u5c0f\u56fe</button>\n'
'  <button class="filter-btn" data-size="medium">\u4e2d\u56fe</button>\n'
'  <button class="filter-btn" data-size="large">\u5927\u56fe</button>\n'
'  &nbsp;&nbsp;<label>\u641c\u7d22\uff1a</label>\n'
'  <input class="search" id="searchBox" placeholder="\u6587\u4ef6\u540d / PDF \u540d\u79f0 / \u7d22\u5f15...">\n'
'</div>\n'
'<div id="resultTip" style="padding:0 0 12px 4px;color:#888;font-size:13px"></div>\n'
'<div class="gallery" id="gallery"></div>\n'
'<div class="modal" id="modal">\n'
'  <div class="modal-content">\n'
'    <div class="modal-hdr">\n'
'      <h2 id="modalTitle"></h2>\n'
'      <button class="close" onclick="closeM()">&times;</button>\n'
'    </div>\n'
'    <div class="modal-body">\n'
'      <div class="src-hlgt">\n'
'        <h4>&#x1f4c1; \u6765\u6e90 PDF</h4>\n'
'        <div class="pdf-name" id="modalPdfName"></div>\n'
'        <div class="pdf-info" id="modalPdfInfo"></div>\n'
'      </div>\n'
'      <img class="modal-img" id="modalImg" src="" alt="">\n'
'      <div class="modal-grid">\n'
'        <div class="modal-sec">\n'
'          <h3>\u57fa\u672c\u4fe1\u606f</h3>\n'
'          <div class="modal-row"><span class="lbl">\u6587\u4ef6\u540d</span><span class="val" id="mFn"></span></div>\n'
'          <div class="modal-row"><span class="lbl">\u5c3f\u5bf8</span><span class="val" id="mDim"></span></div>\n'
'          <div class="modal-row"><span class="lbl">\u9762\u79ef</span><span class="val" id="mArea"></span></div>\n'
'          <div class="modal-row"><span class="lbl">\u5927\u5c0f</span><span class="val" id="mSz"></span></div>\n'
'          <div class="modal-row"><span class="lbl">\u683c\u5f0f</span><span class="val" id="mFmt"></span></div>\n'
'        </div>\n'
'        <div class="modal-sec">\n'
'          <h3>\u6765\u6e90\u4fe1\u606f</h3>\n'
'          <div class="modal-row"><span class="lbl">PDF</span><span class="val" id="mPdf"></span></div>\n'
'          <div class="modal-row"><span class="lbl">\u9875\u7801</span><span class="val" id="mPage"></span></div>\n'
'          <div class="modal-row"><span class="lbl">\u56fe\u7247\u5e8f\u53f7</span><span class="val" id="mIdx"></span></div>\n'
'        </div>\n'
'      </div>\n'
'      <div class="btns">\n'
'        <button class="btn btn-primary" onclick="openOrig()">&#x1f5bc; \u5168\u5c4f\u67e5\u770b</button>\n'
'        <button class="btn btn-outline" onclick="copyPath()">&#x1f4cb; \u590d\u5236\u8def\u5f84</button>\n'
'      </div>\n'
'    </div>\n'
'  </div>\n'
'</div>\n'
'</div>\n'
'<script>\n' + JS + '\n</script>\n'
'</body>\n</html>'
        )
        out_html = self.analysis_dir / "index_enhanced.html"
        with open(out_html, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"      -> HTML: {out_html.name}")
        return out_html

    def update(self):
        self._load_state()
        changes = self._check_changes()
        if not changes["changed"]:
            print("  \u2713 \u65e0\u53d8\u5316\uff0c\u8df3\u8fc7 [" + self.name + "]")
            return False
        print("\n  \u25b6 \u68c0\u6d4b\u5230\u53d8\u5316: \u65b0\u589e " + str(len(changes["added"])) + " | \u5220\u9664 " + str(len(changes["removed"])) + " | \u4fee\u6539 " + str(len(changes["modified"])))
        print("  \u25b6 \u5f00\u59cb\u63d0\u53d6\u56fe\u7247...")
        images, pdf_refs, total_kb = self._extract_all()
        self._generate_html(images, pdf_refs)
        with open(self.meta_file, "w", encoding="utf-8") as f:
            json.dump(images, f, ensure_ascii=False, indent=2)
        with open(self.pdf_ref_file, "w", encoding="utf-8") as f:
            json.dump(pdf_refs, f, ensure_ascii=False, indent=2)
        pdfs = sorted(self.pdf_dir.glob("*.pdf"))
        self._state["pdf_hashes"] = {p.name: self._hash(p) for p in pdfs}
        self._state["last_update"] = datetime.now().isoformat()
        self._state["image_count"] = len(images)
        self._state["total_size_mb"] = total_kb / 1024
        self._save_state()
        print("\n  \u2713 [" + self.name + "] \u66f4\u65b0\u5b8c\u6210: " + str(len(images)) + " \u5f20\u56fe\u7247, " + ("%.1f" % (total_kb/1024)) + " MB")
        return True

def main():
    script_dir = Path(__file__).parent.resolve()
    config_file = script_dir / "projects.json"
    if not config_file.exists():
        print("[\u9519\u8bef] \u627e\u4e0d\u5230\u914d\u7f6e\u6587\u4ef6: " + str(config_file))
        print("\u8bf7\u590d\u5236 projects.example.json \u4e3a projects.json \u5e76\u586b\u5199\u8def\u5f84\u3002")
        input("\u6309\u56de\u8f66\u9000\u51fa...")
        sys.exit(1)
    with open(config_file, "r", encoding="utf-8") as f:
        projects = json.load(f)
    print("="*60)
    print("  PDF \u56fe\u7247\u5e93\u81ea\u52a8\u66f4\u65b0\u7cfb\u7edf v2.0")
    print("="*60)
    for cfg in projects:
        updater = GalleryUpdater(cfg)
        updater.update()
    print("\n" + "="*60)
    print("  \u6240\u6709\u9879\u76ee\u5904\u7406\u5b8c\u6bd5")
    print("="*60)

if __name__ == "__main__":
    main()