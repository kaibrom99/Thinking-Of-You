"""Stores, product-page rules, and category guessing for Thinking of You."""
import re
from urllib.parse import urlparse

# domain: (store name, product-page path pattern, product-id pattern, default category)
# Amazon, Etsy, Target, Walmart, eBay and Shein are tested. The rest are best guesses until tried on real pages.
STORES = {
    "amazon.com": ("Amazon", r"/(dp|gp/product)/", r"/(?:dp|gp/product)/([A-Z0-9]{10})", ""),
    "etsy.com": ("Etsy", r"/listing/", r"/listing/(\d+)", ""),
    "target.com": ("Target", r"/p/", r"/A-(\d+)", ""),
    "walmart.com": ("Walmart", r"/ip/", r"/ip/(?:[^/]+/)?(\d+)", ""),
    "ebay.com": ("eBay", r"/itm/", r"/itm/(?:[^/]+/)?(\d+)", ""),
    "shein.com": ("SHEIN", r"-p-\d+", r"-p-(\d+)", "Clothes"),
    "sephora.com": ("Sephora", r"/product/", r"[-/](P\d+)", "Self-care & beauty"),
    "ulta.com": ("Ulta Beauty", r"/p/", r"/(pimprod\d+|xlsImpprod\d+)", "Self-care & beauty"),
    "lululemon.com": ("Lululemon", r"/p/", r"/(prod\d+)", "Clothes"),
    "nike.com": ("Nike", r"/t/", r"/t/[^/]+/([A-Za-z0-9-]+)", "Sports & fitness"),
    "urbanoutfitters.com": ("Urban Outfitters", r"/shop/", r"/shop/([^/]+)", "Clothes"),
    "asos.com": ("ASOS", r"/prd/", r"/prd/(\d+)", "Clothes"),
    "gymshark.com": ("Gymshark", r"/products/", r"/products/([^/]+)", "Sports & fitness"),
    "footlocker.com": ("Foot Locker", r"/product/", r"/([A-Za-z0-9]+)\.html", "Shoes"),
    "gamestop.com": ("GameStop", r"\d{5,}\.html$", r"(\d{5,})\.html", "Tech & gadgets"),
    "bestbuy.com": ("Best Buy", r"\.p$", r"(\d+)\.p$", "Tech & gadgets"),
    "lego.com": ("LEGO", r"/product/", r"/product/[^/]*?-?(\d+)/?$", "Toys & games"),
    "barnesandnoble.com": ("Barnes & Noble", r"/w/", r"/w/[^/]+/(\d+)", "Books & media"),
    "fivebelow.com": ("Five Below", r"/products/", r"/products/([^/]+)", ""),
    "depop.com": ("Depop", r"/products/", r"/products/([^/]+)", "Clothes"),
    "poshmark.com": ("Poshmark", r"/listing/", r"/listing/[^/]*-([0-9a-f]{24})", "Clothes"),
}


def _find(url: str):
    host = urlparse(url).netloc.lower()
    for domain, info in STORES.items():
        if host == domain or host.endswith("." + domain):
            return domain, info
    return None, None


def store_name(url: str) -> str:
    _, info = _find(url or "")
    return info[0] if info else ""


# Pages on a store's site that are never products (keep in sync with reader.js)
NOT_PRODUCT_PATH = re.compile(r"/(checkout|cart|bag|basket|payment|orders?|login|signin|sign-in|account|wishlist|favorites)(/|$)", re.I)
NOT_PRODUCT_TITLE = re.compile(r"^\s*(checkout|(shopping |my |your )?(cart|bag|basket)|sign in|log in|login|"
                               r"order (confirmation|summary)|payment)\b", re.I)


def is_product_url(url: str) -> bool:
    _, info = _find(url)
    path = urlparse(url).path
    return bool(info) and re.search(info[1], path) is not None and not NOT_PRODUCT_PATH.search(path)


def looks_like_product(title: str) -> bool:
    return not NOT_PRODUCT_TITLE.search(title or "")


def product_key(url: str) -> str:
    """Same product, same key, even if the links look different (slugs, tracking parts)."""
    domain, info = _find(url)
    p = urlparse(url)
    if info:
        m = re.search(info[2], p.path)
        if m:
            return f"{domain}:{m.group(1)}"
    return f"{p.scheme}://{p.netloc}{p.path}"


CATEGORIES = ["Self-care & beauty", "Clothes", "Shoes", "Accessories & jewelry", "Food & drink", "Home & decor",
              "Tech & gadgets", "Sports & fitness", "Books & media", "Toys & games", "Hobbies & crafts", "Pets", "Other"]

# Checked in this order; the first category with a matching word wins.
_RULES = [
    ("Shoes", "sneaker|shoe|boot|sandal|slipper|loafer|heel|cleat|flip flop|clog"),
    ("Sports & fitness", "weight lifting|lifting|gym|workout|yoga|dumbbell|kettlebell|resistance band|fitness|pilates|"
                         "treadmill|running|hiking|camping|basketball|football|soccer|tennis|golf|water bottle"),
    ("Self-care & beauty", "skincare|skin care|cleanser|moisturizer|serum|lotion|shampoo|conditioner|makeup|lipstick|"
                           "lip gloss|lip balm|mascara|foundation|concealer|blush|bronzer|eyeshadow|perfume|fragrance|"
                           "cologne|sunscreen|body wash|body scrub|bath bomb|nail polish|face mask|hair mask|hair dryer|"
                           "razor|toner|spa|essential oil|deodorant|toothbrush|massage"),
    ("Tech & gadgets", "headphone|earbud|airpod|speaker|charger|charging|cable|laptop|tablet|ipad|phone case|smartwatch|"
                       "camera|keyboard|mouse|monitor|console|controller|gaming|video game|usb|bluetooth|power bank|"
                       "drone|projector|e-reader|kindle"),
    ("Books & media", "book|novel|paperback|hardcover|cookbook|manga|comic|vinyl|record player|dvd|blu-ray|audiobook"),
    ("Toys & games", "lego|toy|puzzle|board game|card game|doll|plush|stuffed|action figure|playset|building set|nerf"),
    ("Pets", "dog|cat|pet|puppy|kitten|leash|aquarium"),
    ("Hobbies & crafts", "craft|knitting|crochet|yarn|embroidery|paint|sketchbook|art supplies|journal|planner|sticker|"
                         "diy|sewing|calligraphy|scrapbook"),
    ("Home & decor", "blanket|throw|pillow|candle|vase|lamp|rug|decor|mug|kitchen|towel|bedding|picture frame|wall art|"
                     "diffuser|planter|plant|curtain|mirror|storage|organizer|cutting board|cookware|bowl|tumbler"),
    ("Accessories & jewelry", "necklace|bracelet|ring|earring|watch|sunglasses|backpack|handbag|purse|wallet|belt|scarf|"
                              "hat|beanie|glove|jewelry|hair clip|scrunchie|keychain|tote|bag|strap|lanyard|bangle|cuff|brooch|pendant|anklet|choker"),
    ("Clothes", "shirt|tee|t-shirt|sweatshirt|hoodie|jacket|coat|dress|jeans|pants|leggings|shorts|skirt|sweater|"
                "cardigan|pajama|bra|sock|underwear|swimsuit|bikini|outfit|top|blouse|jumpsuit|romper|costume|vest|"
                "trouser|jogger|tank|bodysuit|sweatpants|robe|apparel"),
    ("Food & drink", "coffee|tea|chocolate|snack|candy|cookie|sauce|spice|wine|gourmet|jerky|honey|granola|popcorn|"
                     "protein bar|cereal|syrup|olive oil|gift basket|latte|matcha|ramen|vegetable|fruit|salad|dip|cheese|pasta|bread|pizza|peanut butter|cake|juice|soda|cracker|trail mix"),
]
_COMPILED = [(cat, re.compile(r"\b(?:%s)(?:s|es)?\b" % "|".join(map(re.escape, words.split("|"))), re.I))
             for cat, words in _RULES]


# Stores that mostly sell one kind of thing: if the title gives no hint, trust the store over the description.
SPECIALTY = {"Sephora", "Ulta Beauty", "LEGO", "Barnes & Noble", "GameStop", "Best Buy", "Foot Locker"}


def guess_category(title: str, description: str = "", url: str = "") -> str:
    """Keyword guess from the title, then the store's usual category (specialty stores), then the description."""
    for cat, rx in _COMPILED:
        if rx.search(title or ""):
            return cat
    _, info = _find(url or "")
    default = info[3] if info and info[3] else ""
    if default and info[0] in SPECIALTY:
        return default
    for cat, rx in _COMPILED:
        if rx.search(description or ""):
            return cat
    return default or "Other"