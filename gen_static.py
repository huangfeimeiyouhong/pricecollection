# -*- coding: utf-8 -*-
"""生成静态前端产物到 public/ 目录（供 Cloudflare Pages 静态托管）。

用法:
  python gen_static.py

产物:
  public/data.json         全量数据（价格快照 + 基准商品库 + 绑定），前端只读 + localStorage 缓存
  public/index.html        主页面（价格对比），由 price-collector.html 拷贝
  public/market-price.html 市场价查询页，由 market-price.html 拷贝
  public/static-data.js    共享的静态数据加载/缓存逻辑

部署:
  npx wrangler pages deploy public
"""
import os
import shutil

import collect

ROOT = os.path.dirname(os.path.abspath(__file__))
PUBLIC = os.path.join(ROOT, "public")


def main():
    os.makedirs(PUBLIC, exist_ok=True)

    # 1) 全量数据 JSON
    collect.dump_static(PUBLIC)

    # 2) 拷贝页面与共享脚本
    shutil.copy(os.path.join(ROOT, "static-data.js"), os.path.join(PUBLIC, "static-data.js"))
    shutil.copy(os.path.join(ROOT, "export-excel.js"), os.path.join(PUBLIC, "export-excel.js"))
    shutil.copy(os.path.join(ROOT, "xlsx.full.min.js"), os.path.join(PUBLIC, "xlsx.full.min.js"))
    shutil.copy(os.path.join(ROOT, "price-collector.html"),
                os.path.join(PUBLIC, "price-collector.html"))
    # 主入口命名为 index.html，Cloudflare Pages 根路径直接可访问
    shutil.copy(os.path.join(ROOT, "price-collector.html"),
                os.path.join(PUBLIC, "index.html"))
    shutil.copy(os.path.join(ROOT, "market-price.html"),
                os.path.join(PUBLIC, "market-price.html"))

    print("\npublic/ 已就绪，可部署到 Cloudflare Pages：")
    print("  npx wrangler pages deploy public")


if __name__ == "__main__":
    main()
