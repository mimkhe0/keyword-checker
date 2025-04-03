# -*- coding: utf-8 -*-
"""
Created on Thu Apr  3 15:21:24 2025

@author: Cypher System
"""

from flask import Flask, render_template, request, send_file, after_this_request
import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import logging
import re
import uuid

# تعریف اپلیکیشن Flask
app = Flask(__name__)

# تنظیمات لاگ
logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# چک کردن داخلی بودن URL
def is_internal_url(base_url, url):
    parsed_url = urlparse(url)
    return parsed_url.netloc == urlparse(base_url).netloc

# گرفتن URLهای داخلی از صفحه
def get_urls(website, limit=100):
    urls = set()
    try:
        res = requests.get(website, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('/'):
                href = urljoin(website, href)
            elif not href.startswith('http'):
                continue
            if is_internal_url(website, href):
                urls.add(href)
    except requests.exceptions.RequestException as e:
        logging.error(f"[!] خطا توی گرفتن صفحه اصلی ({website}): {e}")
    return list(urls)[:limit]

# بررسی وجود کلمات کلیدی در URLها
def check_keywords(keywords, urls):
    results = []
    url_contents = {}

    for url in urls:
        try:
            if url not in url_contents:
                res = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                res.raise_for_status()
                url_contents[url] = res.text.lower()
        except requests.exceptions.RequestException as e:
            logging.error(f"[!] خطا توی گرفتن URL ({url}): {e}")
            url_contents[url] = None

    for keyword in keywords:
        keyword = keyword.strip().lower()
        found = False
        match_url = "-"
        match_type = "-"
        logging.info(f"🔍 کلمه کلیدی: {keyword}")
        pattern = re.compile(rf'\b{re.escape(keyword)}\b')

        for url, content in url_contents.items():
            if content and pattern.search(content):
                found = True
                match_url = url
                match_type = "body"
                logging.info(f"✅ پیدا شد '{keyword}' توی {url}")
                break

        results.append({
            "Keyword": keyword,
            "Found": "Yes" if found else "No",
            "URL": match_url,
            "Matched In": match_type if found else "-"
        })

    return results

# صفحه اصلی
@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    file_link = None
    if request.method == 'POST':
        website = request.form.get('website', '').strip()
        file = request.files.get('file')

        if not website.startswith(('http://', 'https://')):
            return render_template("index.html", error="لطفاً یه آدرس وب‌سایت معتبر وارد کنید (شروع با http:// یا https://).")

        if file and file.filename:
            try:
                df = pd.read_excel(file)
                if df.empty:
                    return render_template("index.html", error="فایل Excel آپلودشده خالیه.")
                keywords = df.iloc[:, 0].dropna().astype(str).tolist()
                if not keywords:
                    return render_template("index.html", error="هیچ کلمه کلیدی توی ستون اول فایل Excel پیدا نشد.")

                urls = get_urls(website)
                logging.info(f"🌐 {len(urls)} URL توی {website} پیدا شد")

                results = check_keywords(keywords, urls)

                output_filename = f"results_{uuid.uuid4().hex}.xlsx"
                output_df = pd.DataFrame(results)
                output_df.to_excel(output_filename, index=False)
                file_link = "/download?filename=" + output_filename

                return render_template("index.html", results=results, file_link=file_link)

            except Exception as e:
                logging.error(f"خطا توی پردازش فایل: {e}")
                return render_template("index.html", error=f"خطا توی پردازش فایل آپلودشده: {e}")
        else:
            return render_template("index.html", error="لطفاً یه فایل Excel حاوی کلمات کلیدی آپلود کنید.")

    return render_template("index.html", results=results, file_link=file_link)

# مسیر دانلود فایل خروجی
@app.route('/download')
def download():
    filename = request.args.get('filename', 'results.xlsx')
    if os.path.exists(filename):
        @after_this_request
        def remove_file(response):
            try:
                os.remove(filename)
            except Exception as e:
                logging.warning(f"نتونستم فایل رو پاک کنم: {e}")
            return response
        return send_file(filename, as_attachment=True)
    else:
        return "خطا: فایل نتایج پیدا نشد."

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
