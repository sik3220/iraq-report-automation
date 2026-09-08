import re

# 이름 → 보고서 표기

NAME_MAP = {
    # 미국
    "Donald Trump": "Trump 대통령",
    "Trump": "Trump 대통령",
    "도널드 트럼프": "Trump 대통령",
    "트럼프" : "Trump 대통령",
    "Marco Rubio": "Rubio 국무장관",
    "Pete Hegseth": "Hegseth 국방장관",

    # 이라크
    "Ali Al-Zaidi": "Al-Zaidi 총리",
    "Ali Faleh Al-Zaidi": "Al-Zaidi 총리",
    "Zaydi 총리": "Al-Zaidi 총리",
    "Zaidi 총리": "Al-Zaidi 총리",
    "Halbousi": "Al-Halbousi",
    "Al Halbousi": "Al-Halbousi",
    "Al-Halbousi": "Al-Halbousi",
    "Mohammed Shia Al-Sudani": "Al-Sudani 前 총리",
    "Adel Al-Yassiri": "Al-Yassiri NIC 의장",
    "Nouri al-Maliki": "Al-Maliki 前 총리",
    "Qais al-Khazali": "Al-Khazali Asaib Ahl al-Haq 사무총장",
    "Hadi al-Amiri": "Al-Amiri Badr 대표",
    "Ammar al-Hakim": "Al-Hakim 국가역량연합 대표",
    "Muqtada al-Sadr": "Al-Sadr 종교지도자",
    "Maliki": "Al-Maliki",
    "Sudani": "Al-Sudani",
    "Amiri": "Al-Amiri",
    "Yassiri": "Al-Yassiri",
    "Hakim": "Al-Hakim",
    "Sadr": "Al-Sadr",
    "Khazali": "Al-Khazali",

    # 이란
    "Masoud Pezeshkian": "Pezeshkian 대통령",
    "Ali Khamenei": "Khamenei 최고지도자",
    "Mojtaba Khamenei": "Mojtaba 최고지도자",
    "Abbas Araghchi": "Araghchi 외교장관",

    # 이스라엘
    "Benjamin Netanyahu": "Netanyahu 총리",

    # 기타
    "Recep Tayyip Erdogan": "Erdogan 대통령",
    "Vladimir Putin": "Putin 대통령",
}


# Country names use Korean even when personal names use English surnames.
NAME_MAP.update({
    "Iraq": "이라크", "Iran": "이란", "Oman": "오만",
    "United States": "미국", "Israel": "이스라엘",
    "Saudi Arabia": "사우디", "Lebanon": "레바논",
    "Yemen": "예멘", "Australia": "호주",
})
# Match source spellings and already-normalized names in a single pass.
# Longest alternatives first prevent partial surname matches and repeated titles.
_NAME_PATTERN = re.compile(
    r"(?<![A-Za-z0-9])(?:"
    + "|".join(re.escape(name) for name in sorted(set(NAME_MAP) | set(NAME_MAP.values()), key=len, reverse=True))
    + r")(?![A-Za-z0-9])"
)


def replace_names(text: str) -> str:
    return _NAME_PATTERN.sub(lambda match: NAME_MAP.get(match.group(0), match.group(0)), text)
