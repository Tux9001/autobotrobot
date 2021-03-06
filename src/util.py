import re
import datetime
import parsedatetime
import ast
import copy
import random
from dateutil.relativedelta import relativedelta
import json
import discord
import toml

config = toml.load(open("config.toml", "r"))

def timestamp(): return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())

prefixes = {
    # big SI prefixes
    "Y": 24, "Z": 21, "E": 18, "P": 15, "T": 12, "G": 9, "M": 6, "k": 3, "h": 2, "da": 1,
    # small SI prefixes
    "d": -1, "c": -2, "m": -3, "µ": -6, "μ": -6, "u": -6, "n": -9, "p": -12, "f": -15, "a": -18, "z": -21, "y": -24,
    # highly dubiously useful unofficial prefixes
    "R": 27, "r": -27, "Q": 30, "q": -30, "X": 27, "x": -27, "W": 30, "w": -30
}
number = "(-?[0-9]+(?:\.[0-9]+)?)(" + "|".join(prefixes.keys()) + ")?"

# from here: https://github.com/Rapptz/RoboDanny/blob/18b92ae2f53927aedebc25fb5eca02c8f6d7a874/cogs/utils/time.py
short_timedelta_regex = re.compile(f"""
(?:(?P<years>{number})(?:years?|y))?                # e.g. 2y
(?:(?P<months>{number})(?:months?|mo))?             # e.g. 2months
(?:(?P<fortnights>{number})(?:fortnights?|fn|f))?   # e.g. 10fn
(?:(?P<weeks>{number})(?:weeks?|w))?                # e.g. 10w
(?:(?P<days>{number})(?:days?|d))?                  # e.g. 14d
(?:(?P<hours>{number})(?:hours?|h))?                # e.g. 12h
(?:(?P<minutes>{number})(?:minutes?|m))?            # e.g. 10m
(?:(?P<seconds>{number})(?:seconds?|s))?            # e.g. 15s """, re.VERBOSE)

def parse_prefixed(s):
    match = re.match(number, s)
    if not match: raise ValueError("does not match metric-prefixed integer format - ensure prefix is valid")
    num = float(match.group(1))
    prefix = match.group(2)
    if prefix: num *= (10 ** prefixes[prefix])
    return num

def parse_short_timedelta(text):
    match = short_timedelta_regex.fullmatch(text)
    if match is None or not match.group(0): raise ValueError("parse failed")
    data = { k: parse_prefixed(v) if v else 0 for k, v in match.groupdict().items() }
    data["weeks"] += data["fortnights"] * 2
    del data["fortnights"]
    return datetime.datetime.now(tz=datetime.timezone.utc) + relativedelta(**data)

cal = parsedatetime.Calendar()
def parse_humantime(text):
    dt_tuple = cal.nlp(text)
    if dt_tuple: return dt_tuple[0][0]
    else: raise ValueError("parse failed")

def parse_time(text):
    try: return datetime.datetime.strptime(text, "%d/%m/%Y")
    except: pass
    try: return parse_short_timedelta(text)
    except: pass
    try: return parse_humantime(text)
    except: pass
    raise ValueError("time matches no available format")

def format_time(dt):
    return dt.strftime("%H:%M:%S %d/%m/%Y")

timeparts = (
    ("y", "years"),
    ("mo", "months"),
    ("d", "days"),
    ("h", "hours"),
    ("m", "minutes"),
    ("s", "seconds")
)

def format_timedelta(from_, to):
    d = relativedelta(to, from_)
    out = ""
    for short, attr in timeparts:
        x = getattr(d, attr)
        if x != 0: out += str(x) + short
    return "0s" if out == "" else out

CODEBLOCK_REGEX = "^[^`]*```[a-zA-Z0-9_\-+]*\n(.+)```$"
CODELINE_REGEX = "^[^`]*`(.*)`$"
def extract_codeblock(s):
    match1 = re.match(CODEBLOCK_REGEX, s, flags=re.DOTALL)
    match2 = re.match(CODELINE_REGEX, s, flags=re.DOTALL)
    if match1: return match1.group(1)
    elif match2: return match2.group(1)
    else: return s.strip()

# from https://github.com/Gorialis/jishaku/blob/master/jishaku/repl/compilation.py
CORO_CODE = """
async def repl_coroutine():
    import asyncio
    import aiohttp
    import discord
    from discord.ext import commands
"""
async def async_exec(code, loc, glob):
    user_code = ast.parse(code, mode='exec')
    wrapper = ast.parse(CORO_CODE, mode='exec')
    funcdef = wrapper.body[-1]
    funcdef.body.extend(user_code.body)
    last_expr = funcdef.body[-1]

    if isinstance(last_expr, ast.Expr):
        funcdef.body.pop()
        funcdef.body.append(ast.Return(last_expr.value))
    ast.fix_missing_locations(wrapper)

    exec(compile(wrapper, "<repl>", "exec"), loc, glob)
    return await (loc.get("repl_coroutine") or glob.get("repl_coroutine"))()

def make_embed(*, fields=(), footer_text=None, **kwargs):
    embed = discord.Embed(**kwargs)
    for field in fields:
        if len(field) > 2:
            embed.add_field(name=field[0], value=field[1], inline=field[2])
        else:
            embed.add_field(name=field[0], value=field[1], inline=False)
    if footer_text:
        embed.set_footer(text=footer_text)
    return embed

def error_embed(msg, title="Error"): return make_embed(color=config["colors"]["error"], description=msg, title=title)
def info_embed(title, msg, fields=()): return make_embed(color=config["colors"]["info"], description=msg, title=title, fields=fields)

# https://github.com/LyricLy/Esobot/blob/bcc9e548c84ea9b23fc832d0b0aaa8288de64886/cogs/general.py
lyrictable_raw = {
            "a": "а",
            "c": "с",
            "e": "е",
            "s": "ѕ",
            "i": "і",
            "j": "ј",
            "o": "о",
            "p": "р",
            "y": "у",
            "x": "х"
        }
lyrictable = str.maketrans({v: k for k, v in lyrictable_raw.items()})

apioprefixes = ["cryo", "meta", "chrono", "contra", "ortho", "macro", "micro", "apeiro", "Ægypto", "equi", "anglo", "atto", "auro", "Australo"
    "dys", "eu", "femto", "giga", "infra", "Inver", "kilo", "meso", "mono", "nano", "neo", "omni", "pico", "proto", "pseudo", "semi", "quasi",
    "Scando", "silico", "sub", "hyper", "super", "tauto", "topo", "trans", "ultra", "uni", "ur-", "yocto", "zepto", "zetta"]
apioinfixes = ["cryo", "pyro", "chrono", "meta", "anarcho", "arachno", "aqua", "accelero", "hydro", "radio", "xeno", "morto", "thanato", "memeto", 
    "contra", "umbra", "macrono", "acantho", "acousto", "aceto", "acro", "aeolo", "hexa", "aero", "aesthio", "agro", "ferro", "alumino",
    "ammonio", "anti", "ankylo", "aniso", "annulo", "apo", "abio", "archeo", "argento", "arseno", "arithmo", "astro", "atlo", "auto", "axo",
    "azido", "bacillo", "bario", "balneo", "baryo", "basi", "benzo", "bismuto", "boreo", "biblio", "spatio", "boro", "bromo", "brachio",
    "bryo", "bronto", "calci", "caco", "carbo", "cardio", "cata", "iso", "centi", "ceno", "centro", "cero", "chalco", "chemo", "chloro",
    "chiono", "choano", "choro", "chromato", "chromo", "chryso", "chylo", "cine", "circum", "cirro", "climo", "cobalti", "coeno", "conico",
    "cono", "cortico", "cosmo", "crypto", "crano", "crystallo", "cyano", "cyber", "cyclo", "deca", "dendro", "cyno", "dactylo", "poly", "deutero",
    "dia", "digi", "diplo", "docosa", "disto", "dromo", "duo", "dynamo", "econo", "ecclesio", "echino", "eco", "ecto", "electro", "eigen", "eka",
    "elasto", "eicosa", "enviro", "enantio", "endo", "exo", "oeno", "femto", "ergato", "ergo", "etho", "euryo", "extro", "fluoro", "fructo",
    "galacto", "galvano", "glacio", "gibi", "glosso", "gluco", "glyco", "grammatico", "grapho", "gravi", "gyro", "hadro", "halo", "hapto", "hecto",
    "heli", "helio", "helico", "historio", "holo", "hella", "hemi", "hepta", "herpeto", "hiero", "hippo", "homo", "hoplo", "horo", "hyalo", "hyeto",
    "hygro", "hylo", "hypho", "hypno", "hypso", "iatro", "icthyo", "ichno", "icosa", "ideo", "idio", "imido", "info", "infra", "insta", "inter",
    "intro", "iodo", "iono", "irid", "iri", "iridio", "kilo", "diago", "juxta", "juridico", "bureaucrato", "entropo", "karyo", "kineto", "klepto",
    "konio", "kymo", "lamino", "leipdo", "lepto", "levo", "dextro", "lexico", "cognito", "ligno", "limno", "lipo", "litho", "logo", "magneto",
    "magnesio", "mega", "mento", "mercurio", "metallo", "mechano", "meco", "medio", "melo", "mero", "meso", "meteoro", "metro", "micto",
    "mono", "miso", "mnemo", "morpho", "myco", "myo", "myria", "mytho", "nano", "necro", "neo", "neutro", "neuro", "nitro", "nycto", "nucleo",
    "narco", "noto", "octo", "ochlo", "odonto", "oculo", "oligo", "opto", "organo", "ornitho", "osmio", "oneiro", "onto", "oxalo", "pachy",
    "paleo", "pali", "pallado", "pano", "para", "penta", "per", "patho", "pebi", "peloro", "pene", "petro", "pharma", "pheno", "philo", "pico",
    "piezo", "phono", "photo", "phospho", "physio", "physico", "phyto", "pico", "post", "pisci", "placo", "platy", "pleo", "plumbo", "pluto",
    "pneumato", "politico", "proto", "potassio", "proteo", "pseudo", "psycho", "ptero", "pykno", "quasi", "quadri", "recti", "retino", "retro",
    "rheo", "rhino", "rhizo", "rhodo", "roto", "rutheno", "saccharo", "sapo", "sauro", "seismo", "seleno", "septa", "silico", "scoto", "semanto",
    "sialo", "socio", "sodio", "skeleto", "somato", "somno", "sono", "spectro", "speleo", "sphero", "spino", "spiro", "sporo", "stanno", "stato",
    "steno", "stereo", "stegano", "strato", "hyper", "sulpho", "telluro", "stygo", "tachy", "tauto", "taxo", "techno", "tecto", "tele", "teleo",
    "temporo", "tera", "tetra", "thalasso", "thaumato", "thermo", "tephro", "tessera", "thio", "titano", "tomo", "topo", "tono", "tungsto",
    "turbo", "tyranno", "ultra", "undeca", "tribo", "trito", "tropho", "tropo", "uni", "urano", "video", "viro", "visuo", "xantho", "xenna",
    "xeri", "xipho", "xylo", "xyro", "yocto", "yttro", "zepto", "zetta", "zinco", "zirco", "zoo", "zono", "zygo", "templateo", "rustaceo", "mnesto",
    "amnesto", "cetaceo", "anthropo", "ioctlo"]
apiosuffixes = ["hazard", "form"]

def apioform():
    out = ""
    if random.randint(0, 4) == 0:
        out += random.choice(apioprefixes)
    out += "apio"
    i = 1
    while True:
        out += random.choice(apioinfixes)
        if random.randint(0, i) > 0: break
        i *= 2
    out += random.choice(apiosuffixes)
    return out

def unlyric(text):
    return text.translate(lyrictable).replace("\u200b", "")

def gen_codeblock(content):
    return "```\n" + content.replace("```", "\\`\\`\\`")[:1900] + "\n```"

def json_encode(x): return json.dumps(x, separators=(',', ':'))