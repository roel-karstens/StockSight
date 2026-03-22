"""
portfolio.py – Default portfolio definition.

Each entry uses the same dict shape as search.py produces, so the rest
of the app (fetcher, metrics, charts, indicators) needs zero changes.
"""

DEFAULT_PORTFOLIO = [
    {"display": "Adobe Inc. (ADBE)",                       "symbol": "ADBE",    "slug": "ADBE",         "yf_symbol": "ADBE",       "exchange": "",    "name": "Adobe Inc."},
    {"display": "ASML Holding N.V. (ASML)",                "symbol": "ASML",    "slug": "ASML",         "yf_symbol": "ASML",       "exchange": "",    "name": "ASML Holding N.V."},
    {"display": "Constellation Software Inc. (TSX:CSU)",   "symbol": "CSU",     "slug": "tsx/CSU",      "yf_symbol": "CSU.TO",     "exchange": "TSX", "name": "Constellation Software Inc."},
    {"display": "Fair Isaac Corporation (FICO)",            "symbol": "FICO",    "slug": "FICO",         "yf_symbol": "FICO",       "exchange": "",    "name": "Fair Isaac Corporation"},
    {"display": "Alphabet Inc. (GOOG)",                    "symbol": "GOOG",    "slug": "GOOG",         "yf_symbol": "GOOG",       "exchange": "",    "name": "Alphabet Inc."},
    {"display": "Intuit Inc. (INTU)",                      "symbol": "INTU",    "slug": "INTU",         "yf_symbol": "INTU",       "exchange": "",    "name": "Intuit Inc."},
    {"display": "Kelly Partners Group (ASX:KPG)",          "symbol": "KPG",     "slug": "asx/KPG",      "yf_symbol": "KPG.AX",     "exchange": "ASX", "name": "Kelly Partners Group Holdings Limited"},
    {"display": "Lifco AB (STO:LIFCO.B)",                  "symbol": "LIFCO.B", "slug": "sto/LIFCO.B",  "yf_symbol": "LIFCO-B.ST", "exchange": "STO", "name": "Lifco AB (publ)"},
    {"display": "Mastercard Incorporated (MA)",             "symbol": "MA",      "slug": "MA",           "yf_symbol": "MA",         "exchange": "",    "name": "Mastercard Incorporated"},
    {"display": "Meta Platforms, Inc. (META)",              "symbol": "META",    "slug": "META",         "yf_symbol": "META",       "exchange": "",    "name": "Meta Platforms, Inc."},
    {"display": "Microsoft Corporation (MSFT)",             "symbol": "MSFT",    "slug": "MSFT",         "yf_symbol": "MSFT",       "exchange": "",    "name": "Microsoft Corporation"},
    {"display": "NVIDIA Corporation (NVDA)",                "symbol": "NVDA",    "slug": "NVDA",         "yf_symbol": "NVDA",       "exchange": "",    "name": "NVIDIA Corporation"},
    {"display": "Novo Nordisk A/S (NVO)",                   "symbol": "NVO",     "slug": "NVO",          "yf_symbol": "NVO",        "exchange": "",    "name": "Novo Nordisk A/S"},
    {"display": "Ferrari N.V. (RACE)",                      "symbol": "RACE",    "slug": "RACE",         "yf_symbol": "RACE",       "exchange": "",    "name": "Ferrari N.V."},
    {"display": "Taiwan Semiconductor (TSM)",               "symbol": "TSM",     "slug": "TSM",          "yf_symbol": "TSM",        "exchange": "",    "name": "Taiwan Semiconductor Manufacturing Company Limited"},
    {"display": "Visa Inc. (V)",                            "symbol": "V",       "slug": "V",            "yf_symbol": "V",          "exchange": "",    "name": "Visa Inc."},
]
