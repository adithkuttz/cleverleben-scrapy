# clever_spider.py
import re
import scrapy
from urllib.parse import urljoin, urlparse
from ..items import ProductItem

class CleverSpider(scrapy.Spider):
    name = "clever"
    allowed_domains = ["cleverleben.at"]
    start_urls = ["https://www.cleverleben.at/produktauswahl"]
    custom_settings = {
        "ROBOTSTXT_OBEY": True,  # you can override from command line
    }

    def __init__(self, max_items=1000, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.max_items = int(max_items)
        except Exception:
            self.max_items = 1000
        self.seen = set()
        self.item_count = 0
        self._current_url = None

    # ---------- Helpers ----------
    def _abs(self, response, href):
        if not href:
            return None
        return urljoin(response.url, href)

    def _clean_text(self, txt):
        if txt is None:
            return None
        # remove newlines/tabs and collapse spaces
        return re.sub(r'\s+', ' ', txt).strip()

    def _extract_first(self, sel_list):
        """
        sel_list: selector result (list-like) or simple string
        """
        # if it's a selector list (SelectorList), iterate
        try:
            for s in sel_list:
                # selector .get(default="") if available
                if hasattr(s, "get"):
                    t = s.get(default="").strip()
                else:
                    t = str(s).strip()
                if t:
                    return self._clean_text(t)
        except TypeError:
            # maybe a single string
            t = str(sel_list).strip()
            return self._clean_text(t)
        return None

    # ---------- Entry ----------
    def parse(self, response):
        # 1) From start page, go to the 4 main categories
        cat_links = response.css('a[href*="/lebensmittel"]::attr(href)').getall()
        cat_links += response.css('a[href*="/getr"]::attr(href)').getall()
        cat_links += response.css('a[href*="/haushalt"]::attr(href)').getall()
        cat_links += response.css('a[href*="/tier"]::attr(href)').getall()
        # Also catch any direct "produkte/*"
        cat_links += response.css('a[href^="/produkte/"]::attr(href)').getall()

        for href in dict.fromkeys(cat_links):
            url = self._abs(response, href)
            if url:
                yield response.follow(url, callback=self.parse_category, dont_filter=True)

    def parse_category(self, response):
        subcats = response.css('a[href^="/produkte/"]::attr(href)').getall()
        if subcats:
            for href in dict.fromkeys(subcats):
                yield response.follow(href, callback=self.parse_listing)
        else:
            yield from self.parse_listing(response)

    def parse_listing(self, response):
        # Product cards
        product_links = response.css('a[href^="/produkt/"]::attr(href)').getall()
        for href in product_links:
            url = self._abs(response, href)
            if url and url not in self.seen:
                self.seen.add(url)
                yield response.follow(url, callback=self.parse_product)

        if self.item_count >= self.max_items:
            return

        # Pagination: look for link that looks like next page text or ?page=
        next_href = None
        # common "next" anchor
        candidate = response.xpath('//a[contains(., "Next") or contains(., "Weiter") or contains(., "chevron_right")]/@href').get()
        if candidate:
            next_href = candidate
        else:
            # fallback: ?page= links
            pages = response.css('a[href*="?page="]::attr(href)').getall()
            cur = 1
            m = re.search(r'[?&]page=(\d+)', response.url)
            if m:
                cur = int(m.group(1))
            cand = None
            for p in sorted(set(pages)):
                m2 = re.search(r'[?&]page=(\d+)', p)
                if m2 and int(m2.group(1)) == cur + 1:
                    cand = p
                    break
            next_href = cand

        if next_href:
            yield response.follow(next_href, callback=self.parse_listing)

    def parse_product(self, response):
        self._current_url = response.url
        if self.item_count >= self.max_items:
            return

        item = ProductItem()
        item['product_url'] = response.url

        # Name
        name = self._extract_first(response.xpath('//h1/text()'))
        if not name:
            name = self._extract_first(response.css('h1::text'))
        item['product_name'] = name

        # Price (raw with currency if present near top, first occurrence)
        price = self._extract_first(response.xpath('//*[contains(text(), "€")][1]/text()'))
        if not price:
            price = self._extract_first(response.css('*:contains("€")::text'))
        item['price'] = price

        # Currency
        item['currency'] = '€' if price and '€' in price else None

        # normalize regular_price (decimal dot)
        if price:
            # extract number-like portion, allow comma as decimal
            m = re.search(r'([\d\.,]+)', price)
            if m:
                raw = m.group(1)
                # replace comma by dot, then if multiple dots/commas keep last as decimal
                norm = raw.replace(',', '.')
                item['regular_price'] = norm
            else:
                item['regular_price'] = None
        else:
            item['regular_price'] = None

        # Description (first paragraph)
        desc = self._extract_first(response.xpath('//h1/following::p[1]/text()'))
        if not desc:
            desc = self._extract_first(response.xpath('//p[normalize-space()][1]/text()'))
        if not desc:
            desc = self._extract_first(response.xpath('//h2[contains(., "Einfach clever")]/preceding::p[1]/text()'))
        item['product_description'] = desc

        # Product ID "Produkt ID: 27-19989"
        pid_text = self._extract_first(response.xpath('//text()[contains(., "Produkt ID:")]'))
        product_id = None
        if pid_text:
            m = re.search(r'Produkt ID:\s*([A-Za-z0-9\-]+)', pid_text)
            if m:
                product_id = m.group(1)
        item['product_id'] = product_id

        # unique_id from URL trailing digits
        m = re.search(r'(\d+)(?:/)?$', urlparse(response.url).path)
        item['unique_id'] = m.group(1) if m else None

        # Ingredients: line that starts with "Zutaten:"
        ingredients = self._extract_first(response.xpath('//text()[starts-with(normalize-space(), "Zutaten:")]'))
        item['ingredients'] = ingredients

        # Details: under "Produktinformation" section, first text line
        details = self._extract_first(response.xpath('//*[self::h2 or self::h3][normalize-space()="Produktinformation"]/following::*[normalize-space()][1]/text()'))
        item['details'] = details

        # Images: og:image + any commercetools CDN images
        imgs = response.xpath('//meta[@property="og:image"]/@content').getall()
        imgs += response.xpath('//img[contains(@src, "commercetools")]/@src').getall()
        # Normalize and absolutize + unique
        abs_imgs = []
        for u in imgs:
            if not u:
                continue
            u_abs = urljoin(response.url, u)
            if u_abs not in abs_imgs:
                abs_imgs.append(u_abs)
        item['images'] = abs_imgs
        # also set singular name for compatibility
        item['image'] = abs_imgs[0] if abs_imgs else None

        # final cleanup: ensure no weird newlines etc (already done by helpers where applicable)
        for k, v in list(item.items()):
            if isinstance(v, str):
                item[k] = self._clean_text(v)

        self.item_count += 1
        yield item
