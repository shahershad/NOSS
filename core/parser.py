# core/parser.py — parse a single HTML to profile dict + CU blocks
from bs4 import BeautifulSoup

def parse_single_html(html_bytes: bytes):
    soup = BeautifulSoup(html_bytes, "html.parser")

    # Profile
    profile_data = {}
    profile_table = soup.find("table", class_="table")
    if profile_table:
        for row in profile_table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) == 2:
                profile_data[cells[0].get_text(strip=True)] = cells[1].get_text(" ", strip=True)

    # CU blocks
    tables = soup.find_all("table", class_="table")
    cu_blocks = []
    current_cu, current_was, current_pcs = {}, [], []

    for table in tables:
        text = table.get_text(" ", strip=True)

        if "CU CODE" in text and "CU TITLE" in text:
            if current_cu:
                cu_blocks.append({
                    **current_cu,
                    "WORK ACTIVITY": " - ".join(current_was),
                    "PERFORMANCE CRITERIA": " - ".join(current_pcs),
                })
            current_was, current_pcs = [], []
            current_cu = {}

            for row in table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    val = cells[1].get_text(" ", strip=True)
                    if key in ["CU CODE", "CU TITLE", "CU DESCRIPTOR"]:
                        current_cu[key] = val

        elif "WORK ACTIVITIES" in text and "PERFORMANCE CRITERIA" in text:
            rows = table.find_all("tr")[1:]
            for row in rows:
                cells = row.find_all("td")
                if len(cells) == 2:
                    current_was.append(cells[0].get_text(" ", strip=True))
                    current_pcs.append(cells[1].get_text(" ", strip=True))

    if current_cu:
        cu_blocks.append({
            **current_cu,
            "WORK ACTIVITY": " - ".join(current_was),
            "PERFORMANCE CRITERIA": " - ".join(current_pcs),
        })

    return profile_data, cu_blocks
