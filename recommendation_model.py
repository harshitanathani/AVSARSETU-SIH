"""
recommendation_model.py

AVSARSETU - Content-based Internship Recommendation Engine
- Uses TF-IDF (scikit-learn) to vectorize text.
- Uses NLTK for tokenization, stopword removal, lemmatization.
- Computes cosine similarity between a student's profile and internship descriptions.
- Returns top 3-5 recommendations or upskilling course suggestions when no strong match.

How to use:
1. Put students.csv and internships.csv in the same folder (or pass custom paths).
2. Run in training/test mode:
   python recommendation_model.py --students students.csv --internships internships.csv
3. To serve via FastAPI (the module includes a FastAPI `app`):
   uvicorn recommendation_model:app --reload
"""

import os
import re
import argparse
import json
from typing import List, Dict, Any, Optional

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import joblib

# NLTK imports & downloads (used for preprocessing)
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

# FastAPI for serving (optional)
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ---------------------------
# NLTK setup (download if needed)
# ---------------------------
def ensure_nltk_resources():
    """
    Ensure required NLTK resources are available.
    Downloads them if not present.
    """
    resources = ["punkt", "stopwords", "wordnet", "omw-1.4"]
    for res in resources:
        try:
            nltk.data.find(f"tokenizers/{res}") if res == "punkt" else nltk.data.find(f"corpora/{res}")
        except LookupError:
            print(f"Downloading NLTK resource: {res} ...")
            nltk.download(res)

ensure_nltk_resources()
STOPWORDS = set(stopwords.words("english"))
LEMMATIZER = WordNetLemmatizer()

# ---------------------------
# Text preprocessing
# ---------------------------
def preprocess_text(text: str) -> str:
    """
    Clean and preprocess text:
    - lowercasing
    - remove non-alphanumeric characters
    - tokenize (NLTK)
    - remove stopwords (NLTK)
    - lemmatize tokens
    - return cleaned string
    """
    if text is None:
        text = ""
    text = str(text).lower()
    # keep alphanumeric and spaces
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    tokens = nltk.word_tokenize(text)
    tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    tokens = [LEMMATIZER.lemmatize(t) for t in tokens]
    return " ".join(tokens)

# ---------------------------
# Data loading & basic cleaning
# ---------------------------
def load_data(students_path: str, internships_path: str) -> (pd.DataFrame, pd.DataFrame):
    """
    Load students and internships CSV files into DataFrames and fill missing values.
    """
    students_df = pd.read_csv(students_path, dtype=str)
    internships_df = pd.read_csv(internships_path, dtype=str)

    # fill NaNs with empty strings for text concat
    students_df = students_df.fillna("")
    internships_df = internships_df.fillna("")

    return students_df, internships_df

# ---------------------------
# Document creation (concatenate fields)
# ---------------------------
def build_student_document(row: pd.Series) -> str:
    """
    Create a single textual document for a student combining skills & interests (extendable).
    """
    # If your students.csv has more fields (education, projects), include them here.
    fields = []
    if "skills" in row:
        fields.append(str(row.get("skills", "")))
    if "interests" in row:
        fields.append(str(row.get("interests", "")))
    # add any other relevant text fields that may exist in students_df
    for f in ["education", "projects", "bio"]:
        if f in row and str(row.get(f, "")).strip():
            fields.append(str(row.get(f, "")))
    return " ".join(fields).strip()

def build_internship_document(row: pd.Series) -> str:
    """
    Create a single textual document for an internship combining title, description & required_skills.
    """
    parts = []
    for f in ["title", "description", "required_skills"]:
        if f in row and str(row.get(f, "")).strip():
            parts.append(str(row.get(f, "")))
    return " ".join(parts).strip()

# ---------------------------
# Core recommendation function (required signature)
# ---------------------------
def get_recommendations(student_id: str,
                        students_df: pd.DataFrame,
                        internships_df: pd.DataFrame,
                        match_threshold: float = 0.4,
                        top_n: int = 5) -> Dict[str, Any]:
    """
    Calculates and returns internship recommendations for a given student.

    Args:
        student_id: ID of the student (string or numeric convertible to str).
        students_df: DataFrame of students (must contain student_id, skills, interests).
        internships_df: DataFrame of internships (must contain internship_id, title, description, required_skills).
        match_threshold: minimum similarity score (0-1) to consider a "good" match (default 0.4).
        top_n: number of recommendations to return (will be clipped to between 3 and 5 as per spec).

    Returns:
        Dict in one of two formats:
        - Success: {"status":"success", "recommendations":[{internship...}, ...]}
        - Upskill: {"status":"upskill", "message": "...", "courses": [...]}
    """
    # ensure student exists
    student_row = students_df.loc[students_df["student_id"].astype(str) == str(student_id)]
    if student_row.empty:
        return {"status": "error", "message": f"Student ID {student_id} not found."}

    # force top_n to be between 3 and 5 if possible (spec requires 3-5)
    top_n = max(3, min(5, int(top_n)))

    # Build internship document corpus
    internships_docs = internships_df.apply(build_internship_document, axis=1).astype(str)
    internships_docs_clean = internships_docs.apply(preprocess_text).tolist()

    # Fit TF-IDF on internship docs (content-based: internships define the feature space)
    tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    internship_vectors = tfidf.fit_transform(internships_docs_clean)

    # Build and preprocess student doc
    student_doc_raw = build_student_document(student_row.iloc[0])
    student_doc_clean = preprocess_text(student_doc_raw)

    # Transform student doc into vector space
    student_vector = tfidf.transform([student_doc_clean])

    # Compute cosine similarities
    similarities = cosine_similarity(student_vector, internship_vectors).flatten()  # shape (n_internships,)

    # attach scores to internships
    internships_df = internships_df.reset_index(drop=True)  # align indices
    internships_df["match_score"] = similarities

    # sort by similarity descending
    ranked = internships_df.sort_values(by="match_score", ascending=False).reset_index(drop=True)

    # check threshold: if best match below threshold, suggest upskilling
    best_score = float(ranked.loc[0, "match_score"]) if not ranked.empty else 0.0
    if best_score < match_threshold:
        # Recommend upskilling courses based on student's skills
        upskill_courses = recommend_courses_from_skills(student_row.iloc[0].get("skills", "") + " " + student_row.iloc[0].get("interests", ""))
        return {
            "status": "upskill",
            "message": "We couldn't find a strong match. We recommend these courses to boost your profile.",
            "courses": upskill_courses
        }

    # Build recommendations list (take top_n results)
    recommendations = []
    for _, row in ranked.head(top_n).iterrows():
        recommendations.append({
            "internship_id": row.get("internship_id"),
            "title": row.get("title"),
            "match_score": round(float(row.get("match_score", 0.0)), 4)  # keep 4 decimal places
        })

    return {
        "status": "success",
        "recommendations": recommendations
    }

# ---------------------------
# Upskilling course recommender (fallback)
# ---------------------------
COURSE_MAPPING = {
    # simple keyword -> course mapping (Skill India / SWAYAM style names)
    "python": ["Data Science with Python", "Programming in Python"],
    "machine learning": ["Advanced Machine Learning", "Machine Learning Foundations"],
    "ml": ["Advanced Machine Learning"],
    "data": ["Data Analysis with Python", "Data Science with Python"],
    "nlp": ["Natural Language Processing", "NLP with Deep Learning"],
    "deep learning": ["Deep Learning Specialization", "Neural Networks and Deep Learning"],
    "web": ["Full-Stack Web Development", "Frontend Web Development"],
    "html": ["Full-Stack Web Development"],
    "css": ["Full-Stack Web Development"],
    "javascript": ["Full-Stack Web Development"],
    "cloud": ["Cloud Computing Basics", "Cloud Fundamentals (AWS/GCP)"],
    "database": ["Database Management Systems", "SQL for Data Science"],
    "blockchain": ["Blockchain Fundamentals"],
    "iot": ["IoT Fundamentals"],
    "cyber": ["Cybersecurity Essentials"],
    "excel": ["Excel for Data Analysis"]
}

def recommend_courses_from_skills(skills_text: str, top_k: int = 3) -> List[str]:
    """
    Based on keywords found in the student's skills/interests text, suggest a short list of courses.
    If no mapping is found, return generic popular courses.
    """
    cleaned = preprocess_text(skills_text)
    tokens = set(cleaned.split())
    suggestions = []
    for kw, courses in COURSE_MAPPING.items():
        # check token presence or KW as substring
        if kw in cleaned or kw in tokens:
            for c in courses:
                if c not in suggestions:
                    suggestions.append(c)
    # fallback generic courses
    if not suggestions:
        suggestions = [
            "Data Science with Python",
            "Full-Stack Web Development",
            "Fundamentals of Machine Learning"
        ]
    return suggestions[:top_k]

# ---------------------------
# Utility: train & save artifacts (persistent model for serving)
# ---------------------------
def train_and_save_model(internships_df: pd.DataFrame, save_path: str = "avsarsetu_model.joblib") -> None:
    """
    Fit a TF-IDF vectorizer on internship documents and save artifacts to disk:
    - vectorizer
    - internship_vectors (sparse matrix)
    - internships_df (with metadata)
    """
    internships_docs = internships_df.apply(build_internship_document, axis=1).astype(str)
    internships_docs_clean = internships_docs.apply(preprocess_text).tolist()

    tfidf = TfidfVectorizer(ngram_range=(1, 2), max_features=5000)
    internship_vectors = tfidf.fit_transform(internships_docs_clean)

    artifacts = {
        "vectorizer": tfidf,
        "internship_vectors": internship_vectors,
        "internships_df": internships_df.reset_index(drop=True)
    }

    joblib.dump(artifacts, save_path)
    print(f"Model artifacts saved to: {save_path}")

def load_model_artifacts(path: str = "avsarsetu_model.joblib") -> Dict[str, Any]:
    """
    Load previously saved model artifacts.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model artifact not found at: {path}")
    artifacts = joblib.load(path)
    return artifacts

# ---------------------------
# Efficient recommendation using pre-trained artifacts (for API serving)
# ---------------------------
def recommend_with_artifacts(student_profile_text: str,
                             artifacts: Dict[str, Any],
                             top_n: int = 5,
                             match_threshold: float = 0.4) -> Dict[str, Any]:
    """
    Given a student's raw profile text and loaded artifacts, compute recommendations quickly.
    """
    tfidf = artifacts["vectorizer"]
    internship_vectors = artifacts["internship_vectors"]
    internships_df = artifacts["internships_df"].copy()

    student_doc_clean = preprocess_text(student_profile_text)
    student_vector = tfidf.transform([student_doc_clean])

    similarities = cosine_similarity(student_vector, internship_vectors).flatten()
    internships_df["match_score"] = similarities
    ranked = internships_df.sort_values(by="match_score", ascending=False).reset_index(drop=True)

    top_n = max(3, min(5, top_n))
    if ranked.empty or float(ranked.loc[0, "match_score"]) < match_threshold:
        # fallback upskill
        return {
            "status": "upskill",
            "message": "We couldn't find a strong match. We recommend these courses to boost your profile.",
            "courses": recommend_courses_from_skills(student_profile_text)
        }

    recommendations = []
    for _, row in ranked.head(top_n).iterrows():
        recommendations.append({
            "internship_id": row.get("internship_id"),
            "title": row.get("title"),
            "match_score": round(float(row.get("match_score", 0.0)), 4)
        })

    return {
        "status": "success",
        "recommendations": recommendations
    }

# ---------------------------
# FastAPI App (optional) - run via: uvicorn recommendation_model:app --reload
# ---------------------------
app = FastAPI(title="AVSARSETU Recommendation API",
              description="Content-based internship recommender (TF-IDF + Cosine Similarity)",
              version="1.0")

# Load model artifacts on startup if available; otherwise will be trained lazily
ARTIFACTS_PATH = "avsarsetu_model.joblib"
MODEL_ARTIFACTS = None
STUDENTS_DF = None  # if you want to pre-load a students CSV, set this on startup
INTERNSHIPS_DF = None

@app.on_event("startup")
def startup_event():
    global MODEL_ARTIFACTS
    global STUDENTS_DF
    global INTERNSHIPS_DF
    # Try to load artifacts; if absent, nothing fatal (we can still run get_recommendations if user provides CSVs)
    if os.path.exists(ARTIFACTS_PATH):
        MODEL_ARTIFACTS = load_model_artifacts(ARTIFACTS_PATH)
        print("Loaded model artifacts for fast serving.")
    else:
        print("No pre-saved model artifacts found at startup. You may train & save using train_and_save_model().")

class ProfilePayload(BaseModel):
    student_id: Optional[str] = None
    skills: Optional[str] = ""
    interests: Optional[str] = ""
    # Accept arbitrary extra fields via .dict() if needed

@app.post("/recommend/profile")
def recommend_by_profile(payload: ProfilePayload, top_n: int = 5, match_threshold: float = 0.4):
    """
    POST endpoint that accepts a student profile (skills & interests) and returns recommendations.
    Example JSON: {"skills":"Python, Machine Learning", "interests":"NLP, Data"}
    """
    profile_text = ((payload.skills or "") + " " + (payload.interests or "")).strip()
    if not profile_text:
        raise HTTPException(status_code=400, detail="Please provide skills and/or interests in the payload.")

    # If artifacts exist, use them for fast recommendation
    if MODEL_ARTIFACTS:
        result = recommend_with_artifacts(profile_text, MODEL_ARTIFACTS, top_n=top_n, match_threshold=match_threshold)
        return result

    # Otherwise, fallback to a quick TF-IDF fit on provided internships CSV (if available)
    raise HTTPException(status_code=503, detail="Recommendation engine not trained. Please train and save artifacts first.")

@app.get("/recommend/student/{student_id}")
def recommend_by_student_api(student_id: str, students_csv: Optional[str] = None, internships_csv: Optional[str] = None,
                             top_n: int = 5, match_threshold: float = 0.4):
    """
    GET endpoint to recommend by student_id from CSVs. Either:
    - Provide students_csv & internships_csv query params (paths on server), or
    - Place 'students.csv' and 'internships.csv' next to this script and omit params.

    Example: GET /recommend/student/123?students_csv=students.csv&internships_csv=internships.csv
    """
    s_path = students_csv or "students.csv"
    i_path = internships_csv or "internships.csv"
    if not os.path.exists(s_path) or not os.path.exists(i_path):
        raise HTTPException(status_code=400, detail=f"CSV files not found at provided paths: {s_path}, {i_path}")

    students_df, internships_df = load_data(s_path, i_path)
    result = get_recommendations(student_id, students_df, internships_df, match_threshold=match_threshold, top_n=top_n)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return result

# ---------------------------
# CLI entrypoint for training/testing
# ---------------------------
def main_cli(args):
    students_csv = args.students
    internships_csv = args.internships
    model_out = args.model_out

    print("Loading data...")
    students_df, internships_df = load_data(students_csv, internships_csv)
    print(f"Loaded {len(students_df)} students and {len(internships_df)} internships.")

    # Demonstrate usage: train and save model artifacts
    print("Training TF-IDF on internships and saving artifacts...")
    train_and_save_model(internships_df, save_path=model_out)

    # Example: get recommendations for the first student in the CSV (demo)
    if not students_df.empty:
        demo_student_id = students_df.iloc[0]["student_id"]
        print(f"\nDemo: recommendations for student_id = {demo_student_id}")
        recs = get_recommendations(demo_student_id, students_df, internships_df, match_threshold=0.4, top_n=5)
        print(json.dumps(recs, indent=2))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AVSARSETU - Recommendation model trainer & demo")
    parser.add_argument("--students", type=str, default="students.csv", help="Path to students.csv")
    parser.add_argument("--internships", type=str, default="internships.csv", help="Path to internships.csv")
    parser.add_argument("--model_out", type=str, default="avsarsetu_model.joblib", help="Output path for saved artifacts")
    args = parser.parse_args()
    main_cli(args)
