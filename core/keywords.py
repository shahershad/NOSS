# core/keywords.py — canonical keyword bases + variant seeds and builders
import re
from collections import Counter

# === Paste your GREEN_BASE and IR_BASE from your script (unchanged) ===
GREEN_BASE = [
    "artificial intelligence","biofuel","biogas","biomass","building sector",
    "carbon capture and sequestration","clean energy","co-generation",
    "concentrated solar power","digital technology","energy","energy efficiency",
    "energy supply sector","energy utilisation sector","environmentally sound technology",
    "global value chain","green building","green building index","green business",
    "green growth","green house gas","green hydrogen","green manufacturing",
    "green processes","green procurement","green product","green technology","green township",
    "green windows of opportunity","industry 4.0 technology","internet of things","mycrest",
    "national green technology policy","national innovation system","renewable energy",
    "renewable resource","small hydro","solar photovoltaic","sustainable energy",
    "transportation sector","water and waste management sector","wind energy",
    "carbon footprint","decarbonization","climate change mitigation","carbon capture",
    "air quality monitoring","emissions reduction","carbon neutral","air pollution control",
    "clean air","methane emissions","nitrogen oxides reduction","pollution control technology",
    "sustainable transportation","low-carbon fuels","eco-friendly transport",
    "industrial emissions","volatile organic compounds","sulfur oxides reduction",
    "water conservation","waste water treatment","water quality","water management",
    "sustainable water systems","hydrogeology","desalination","water efficiency",
    "rainwater harvesting","watershed restoration","greywater recycling","water purification",
    "water footprint","water stewardship","water infrastructure","flood management",
    "drought resilience","groundwater remediation","irrigation efficiency","stormwater management",
    "solar power","geothermal energy","smart grid","energy storage","energy audit",
    "hydropower","tidal energy","biomass energy","energy management systems","grid modernization",
    "passive house design","energy policy","demand-side management","renewable portfolio standards",
    "circular economy","waste reduction","recycling","upcycling","composting","waste-to-energy",
    "sustainable packaging","landfill diversion","e-waste","zero waste","hazardous waste",
    "industrial symbiosis","product stewardship","material recovery facility","waste auditing",
    "extended producer responsibility","anaerobic digestion","resource recovery","waste disposal",
    "litter prevention","sustainable materials","bio-based materials","life cycle assessment",
    "resource efficiency","green chemistry","bioplastics","recycled content","eco-friendly materials",
    "closed-loop system","sustainable sourcing","fair trade materials","non-toxic materials",
    "material circularity","biomimicry","sustainable forestry","cradle-to-cradle",
    "post-consumer recycled content","material innovation","carbon tax","carbon credit",
    "net zero","energy reduction","heat recovery","sustainability","eco-friendly",
    "environmental standard","environmental sustainability",
    "environmental, social and governance","predictive maintenance","reuse","sustainable development"
]

IR_BASE = [
    "3d printing","additive manufacturing","advanced digital production technology",
    "advanced digitisation","advanced manufacturing","advanced material",
    "artificial intelligence","augmented reality","automation","autonomous robot",
    "autonomous vehicle","big data","biodegradable plastic","biodegradable sensor",
    "biotechnology","blockchain","circular economy","cloud computing",
    "collaborative telepresence","convergent and nature-like technology",
    "cyber-physical system","cybersecurity","data analytic","digital economy",
    "digital technology","digitalisation","digitisation","distributed ledger technology",
    "drone","efficient resource utilisation","emerging technology","frontier technology",
    "generative artificial intelligence","geospatial data monitoring platform",
    "industrial iot","internet of things","machine learning","machine to machine",
    "mass customization","nanotechnology","physical-cyber system","predictive maintenance",
    "quantum computing","robotic","simulation","smart agrofood","smart circular economy",
    "smart city","smart energy","smart factory","smart manufacturing",
    "smart manufacturing systems","social robot","space technology","super computing",
    "system integration","digital trust","data safety","computerization",
    "autonomous mobile robot","smart sensor","manufacturing execution system",
    "risk to manufacturing","threats to manufacturing","healthcare automation","cryptography",
    "cloud security","zero trust architecture","human computer interaction","cyber resilience",
    "enterprise resource planning","data security","data privacy","digital twin",
    "semiconductor design","smart camera","agentic artificial intelligence","vibe marketing",
    "vibe coding","human machine interface","human machine collaboration",
    "verification of information","validation of information","interoperability",
    "ethical standard","data sharing","personal data protection","data transparent",
    "data management","data protection","industry revolution","regulatory compliance",
    "cloud service","real time monitoring","advanced materials","cloud-based systems",
    "data-driven decision making","digital infrastructure","digital transformation",
    "policy framework","prototyping","real-time analytic","technical skills",
    "threat detection","deoxyribonucleic acid data storage"
]

GREEN_BASE_SET = set([b.strip().lower() for b in GREEN_BASE])
IR_BASE_SET    = set([b.strip().lower() for b in IR_BASE])

# ---- Variant seeds (same as your script; trimmed for brevity here). Keep yours. ----
VARIANTS_GREEN_SEED = {
    "internet of things": ["iot","internet-of-things","internet of thing"],
    "solar photovoltaic": ["solar pv","pv solar","solar power"],
    "green house gas": ["greenhouse gas","greenhouse gases","ghg"],
    "carbon capture and sequestration": ["ccs","carbon capture and storage","carbon capture & storage"],
    "co-generation": ["cogeneration","combined heat and power","chp"],
    "energy utilisation sector": ["energy utilization sector"],
    "mycrest": ["my crest"],
    "green product": ["green products"],
    "renewable resource": ["renewable resources"],
    "wind energy": ["wind power"],
    "concentrated solar power": ["csp"],
    "environmentally sound technology": ["est","environmentally sustainable technology","eco-friendly technology"],
    "global value chain": ["global value chains","gvc","gvcs"],
    "national innovation system": ["nis"],
    "green technology": ["green tech"],
    "digital technology": ["digital technologies"],
    "energy management systems": ["ems"],
    "renewable portfolio standards": ["rps"],
    "life cycle assessment": ["lca","life-cycle assessment","lifecycle assessment"],
    "sustainable forestry": ["fsc"],
    "post-consumer recycled content": ["pcr"],
    "environmental, social and governance": ["esg"],
    "recycle": ["recycles","recycled","recycling"],
    "reuse": ["reuses","reused","reusing"],
}

VARIANTS_IR_SEED = {
    "artificial intelligence": ["ai"],
    "machine learning": ["ml"],
    "3d printing": ["3-d printing","3 d printing","3dp"],
    "additive manufacturing": ["am"],
    "cyber-physical system": ["cps","cyber physical system"],
    "digitalisation": ["digitalization"],
    "digitisation": ["digitization"],
    "cybersecurity": ["cyber security"],
    "industrial iot": ["iiot","industrial internet of things"],
    "internet of things": ["iot"],
    "predictive maintenance": ["pdm"],
    "nanotechnology": ["nanotechnologies"],
    "super computing": ["hpc","supercomputing"],
    "robotic": ["robotics","robotically"],
    "data analytic": ["data analytics"],
    "cloud computing": ["cloud-computing"],
    "blockchain": ["dlt","distributed ledger"],
    "smart factory": ["smart factories","intelligent factory"],
    "smart manufacturing systems": ["smart manufacturing system","intelligent manufacturing systems"],
    "human computer interaction": ["hci","human–computer interaction"],
    "human machine interface": ["hmi","human–machine interface"],
    "enterprise resource planning": ["erp"],
    "manufacturing execution system": ["mes"],
    "zero trust architecture": ["zta"],
    "deoxyribonucleic acid data storage": ["dna data storage"],
    "monitor": ["monitors","monitored","monitoring"],
    "validate": ["validates","validated","validating"],
    "verify": ["verifies","verified","verifying"],
    "simulate": ["simulates","simulated","simulating"],
    "automate": ["automates","automated","automating"],
}

# ============================================================
# 2b) BAHASA MELAYU VARIANTS (map to same English bases)
# ============================================================

BM_GREEN_VARIANTS = {
    "green technology": ["teknologi hijau"],
    "renewable energy": [
        "tenaga boleh baharu","tenaga boleh diperbaharui","tenaga diperbaharui",
        "tenaga lestari","tenaga mampan"
    ],
    "solar photovoltaic": ["fotovoltaik suria","pv suria","fotovolta suria"],
    "wind energy": ["tenaga angin","kuasa angin"],
    "biofuel": ["bahan api bio"],
    "biogas": ["biogas"],
    "biomass": ["biomas"],
    "energy efficiency": ["kecekapan tenaga","keberkesanan tenaga"],
    "clean energy": ["tenaga bersih"],
    "environmentally sound technology": ["teknologi mesra alam","teknologi mesra-alam"],
    "global value chain": ["rantaian nilai global","rantaian nilai sejagat","gvc"],
    "green building": ["bangunan hijau"],
    "green building index": ["indeks bangunan hijau","gbi"],
    "green business": ["perniagaan hijau"],
    "green growth": ["pertumbuhan hijau"],
    "green house gas": ["gas rumah hijau","gas rumah kaca","ghg"],
    "green hydrogen": ["hidrogen hijau"],
    "green manufacturing": ["pembuatan hijau","perkilangan hijau"],
    "green processes": ["proses hijau"],
    "green procurement": ["perolehan hijau"],
    "green product": ["produk hijau","produk-produk hijau"],
    "carbon capture and sequestration": [
        "penangkapan dan penyimpanan karbon","penangkapan karbon dan penyimpanan",
        "penangkapan karbon","penyimpanan karbon","ccs"
    ],
    "co-generation": ["kogenerasi","penjanaan bersama","gabungan haba dan kuasa","chp"],
    "concentrated solar power": ["kuasa suria tertumpu","csp"],
    "energy supply sector": ["sektor bekalan tenaga"],
    "energy utilisation sector": ["sektor penggunaan tenaga","sektor utiliti tenaga"],
    "energy": ["tenaga"],
    "renewable resource": ["sumber boleh baharu","sumber boleh diperbaharui"],
    "small hydro": ["hidro kecil","mini hidro"],
    "transportation sector": ["sektor pengangkutan"],
    "water and waste management sector": ["sektor pengurusan air dan sisa","pengurusan air dan sisa"],
    "industry 4.0 technology": ["teknologi industri 4.0","teknologi perindustrian 4.0"],
    "digital technology": ["teknologi digital","teknologi-teknologi digital"],
    "internet of things": ["internet benda","internet benda-benda","iot"],
    "national green technology policy": ["dasar teknologi hijau negara"],
    "national innovation system": ["sistem inovasi negara"],
    "mycrest": ["mycrest","my crest"],
    "green township": ["bandar hijau","perbandaran hijau"],
    "green windows of opportunity": ["tingkap peluang hijau","ruang peluang hijau"],
}

BM_IR_VARIANTS = {
    "artificial intelligence": ["kecerdasan buatan","kebijaksanaan buatan","ai"],
    "machine learning": ["pembelajaran mesin","ml"],
    "big data": ["data raya","data besar"],
    "cloud computing": ["pengkomputeran awan","komputasi awan"],
    "cybersecurity": ["keselamatan siber","keselamatan-siber"],
    "blockchain": ["rantaian blok","lejar teragih","lejar diedarkan","dlt"],
    "internet of things": ["internet benda","internet benda-benda","iot"],
    "industrial iot": ["iot perindustrian","iot industri","iiot","internet benda perindustrian"],
    "digitalisation": ["pendigitalan","digitalisasi"],
    "digitisation": ["pendigitian","pendigitan"],
    "augmented reality": ["realiti terimbuh","ar"],
    "robotic": ["robotik"],
    "3d printing": ["percetakan 3d","pencetakan 3d","cetak 3d","3-d printing","3 d printing"],
    "additive manufacturing": ["pembuatan aditif","perkilangan aditif"],
    "predictive maintenance": ["penyelenggaraan ramalan","penyelenggaraan prediktif"],
    "quantum computing": ["pengkomputeran kuantum","komputasi kuantum"],
    "nanotechnology": ["nanoteknologi","teknologi nano"],
    "simulation": ["simulasi"],
    "autonomous vehicle": ["kenderaan autonomi"],
    "autonomous robot": ["robot autonomi"],
    "smart city": ["bandar pintar","bandar bijak"],
    "smart factory": ["kilang pintar","kilang bijak"],
    "smart manufacturing": ["pembuatan pintar","perkilangan pintar"],
    "smart manufacturing systems": ["sistem pembuatan pintar","sistem perkilangan pintar"],
    "smart energy": ["tenaga pintar"],
    "circular economy": ["ekonomi kitaran"],
    "space technology": ["teknologi angkasa"],
    "drone": ["dron","drone"],
    "data analytic": ["analitik data","analisis data"],
    "distributed ledger technology": ["teknologi lejar teragih","teknologi lejar diedarkan"],
    "geospatial data monitoring platform": ["platform pemantauan data geospatial","platform pemantauan geospatial"],
    "convergent and nature-like technology": ["teknologi konvergen dan menyerupai alam"],
    "physical-cyber system": ["sistem fizikal-siber","sistem siber-fizikal"],
    "cyber-physical system": ["sistem siber-fizikal","sistem fizikal-siber","cps"],
    "digital economy": ["ekonomi digital"],
    "frontier technology": ["teknologi hadapan","teknologi sempadan"],
    "emerging technology": ["teknologi muncul"],
    "system integration": ["integrasi sistem"],
    "social robot": ["robot sosial"],
    "mass customization": ["penyesuaian massa","penyesuaian besar-besaran"],
    "machine to machine": ["mesin ke mesin","m2m"],
    "super computing": ["pengkomputeran berprestasi tinggi","pengkomputeran prestasi tinggi","hpc"],
    "dna data storage": ["penyimpanan data dna"],
    "advanced manufacturing": ["pembuatan termaju","perkilangan termaju"],
    "advanced material": ["bahan termaju"],
}

# Merge BM variants into seeds
for base, extras in BM_GREEN_VARIANTS.items():
    VARIANTS_GREEN_SEED.setdefault(base, []).extend(extras)
for base, extras in BM_IR_VARIANTS.items():
    VARIANTS_IR_SEED.setdefault(base, []).extend(extras)

# -------- Helpers to build variant maps & regex ----------
def _tokenize(p: str):
    return [t for t in re.split(r"[\s\-]+", p.strip().lower()) if t]

def _morph_last_token_forms(tok: str):
    t = tok.lower()
    forms = {t}
    if t.endswith("y"):
        stem = t[:-1]
        forms.update({t, stem + "ies", stem + "ied", stem + "ying", t + "s"})
    else:
        forms.update({t + "s", t + "es", t + "ed", t + "ing"})
    if t.endswith(("al", "ic")):
        forms.add(t + "ly")
    return forms

def expand_phrase_variants(phrase: str):
    toks = _tokenize(phrase)
    if not toks: return set()
    last_forms = _morph_last_token_forms(toks[-1])
    if len(toks) == 1:
        return set(last_forms) | {toks[0]}
    stem_space  = " ".join(toks[:-1])
    stem_hyphen = "-".join(toks[:-1])
    out = {phrase.lower()}
    for lf in last_forms:
        out.add(f"{stem_space} {lf}")
        out.add(f"{stem_hyphen}-{lf}")
    return out

def build_variant_map(base_list, seed_dict):
    base_set = set([b.strip().lower() for b in base_list])
    variant_to_base = {}
    for base in base_set:
        seeds = {base}
        if base in seed_dict:
            seeds.update([v.strip().lower() for v in seed_dict[base]])
        all_variants = set()
        for s in seeds:
            all_variants |= expand_phrase_variants(s)
            all_variants.add(s)  # exact
        for v in all_variants:
            variant_to_base[v] = base
    return base_set, variant_to_base
