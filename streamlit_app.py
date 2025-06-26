import streamlit as st
import pandas as pd
from rapidfuzz import fuzz
from metaphone import doublemetaphone
from collections import Counter
import re
import io

# -------------------- CONFIG --------------------
MATCH_THRESHOLD_MAIN = 70
MATCH_THRESHOLD_LOOSE = 60
PARTIAL_THRESHOLD = 70
SET_THRESHOLD = 80
PARTIAL_TOKEN_PHONETIC_THRESHOLD = 60

# -------------------- HELPERS --------------------
def normalize_name(name):
    name = str(name).lower().strip()
    name = re.sub(r'[^a-z\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name

def get_core_name(name):
    return re.split(r'\bso\b|\bs/o\b|\bw/o\b|\bd/o\b|:', name)[0].strip()

def build_name_dictionary(df, column):
    all_tokens = df[column].apply(normalize_name).str.split().explode()
    common_tokens = [token for token, count in Counter(all_tokens).items() if count > 1 and len(token) > 2]
    return set(common_tokens)

def split_joined_name(name, dictionary):
    temp = name
    splits = []
    for word in sorted(dictionary, key=len, reverse=True):
        if word in temp:
            splits.append(word)
            temp = temp.replace(word, '', 1)
    if temp:
        splits.append(temp)
    return ' '.join(splits).strip()

def phonetic_compare(name1, name2):
    ph1 = set(filter(None, doublemetaphone(name1)))
    ph2 = set(filter(None, doublemetaphone(name2)))
    return bool(ph1 & ph2)

def fuzzy_token_match(name1, name2):
    tokens = name2.split()
    for token in tokens:
        score = fuzz.partial_ratio(name1, token)
        if score >= PARTIAL_TOKEN_PHONETIC_THRESHOLD or phonetic_compare(name1, token):
            return True
    return False

def smart_match(row, dictionary):
    farmer_raw = str(row['farmerName'])
    pfms_raw = str(row['pfmsFarmerName'])

    farmer_norm = normalize_name(farmer_raw)
    pfms_norm = normalize_name(pfms_raw)

    pfms_core = get_core_name(pfms_norm)
    pfms_comp = pfms_core if len(pfms_core.split()) >= 1 else pfms_norm

    farmer_split = split_joined_name(farmer_norm, dictionary)

    score_main = fuzz.token_sort_ratio(farmer_split, pfms_comp)
    score_partial = fuzz.partial_ratio(farmer_split, pfms_comp)
    score_set = fuzz.token_set_ratio(farmer_split, pfms_comp)

    ph_match = phonetic_compare(farmer_split, pfms_comp) or phonetic_compare(farmer_norm, pfms_comp)
    token_match = fuzzy_token_match(farmer_norm, pfms_norm)

    if score_main >= MATCH_THRESHOLD_MAIN or \
       (score_main >= MATCH_THRESHOLD_LOOSE and score_partial > PARTIAL_THRESHOLD and score_set > SET_THRESHOLD) or \
       ph_match or token_match:
        remark = "Name matching"
    else:
        remark = "Mismatch"

    return pd.Series([farmer_split, score_main, score_partial, score_set, ph_match, token_match, remark])

# -------------------- STREAMLIT APP --------------------
st.set_page_config(page_title="Smart Name Matcher", layout="wide")
st.title("🔍 Smart Name Matching App")

uploaded_file = st.file_uploader("Upload Excel File (with `farmerName` and `pfmsFarmerName` columns)", type="xlsx")

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file)
        df.columns = df.columns.str.strip()

        if 'farmerName' not in df.columns or 'pfmsFarmerName' not in df.columns:
            st.error("❌ Columns 'farmerName' and 'pfmsFarmerName' are required in the Excel file.")
        else:
            with st.spinner("Matching names..."):
                name_dict = build_name_dictionary(df, 'pfmsFarmerName')
                df[['farmer_split', 'score_main', 'score_partial', 'score_set', 'phonetic_match', 'token_match', 'remark']] = df.apply(
                    lambda row: smart_match(row, name_dict), axis=1
                )
                st.success("✅ Matching complete!")

                st.dataframe(df[['farmerName', 'pfmsFarmerName', 'remark']].head(100), use_container_width=True)

                output = io.BytesIO()
                df.to_excel(output, index=False)
                st.download_button("📥 Download Full Excel Result", output.getvalue(), file_name="smart_name_matching_result.xlsx")
    except Exception as e:
        st.error(f"❌ Error: {e}")