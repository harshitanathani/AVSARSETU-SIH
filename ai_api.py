from fastapi import FastAPI
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json
import re

app = FastAPI(title="AVSARSETU Recommendation API")

# Simple preprocessing
def simple_preprocess(text):
    if text is None:
        text = ""
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    tokens = text.split()
    stopwords = {"a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he", "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "will", "with", "i", "you", "this", "but", "they", "have"}
    tokens = [t for t in tokens if t not in stopwords and len(t) > 1]
    return " ".join(tokens)

# Load sample data
internships_data = [
    {"internship_id": "201", "title": "Data Analyst Intern", "description": "Analyze datasets, build dashboards and reports", "required_skills": "Python, Data Analysis, SQL"},
    {"internship_id": "202", "title": "Web Developer Intern", "description": "Develop responsive web applications with modern UI", "required_skills": "HTML, CSS, JavaScript"},
    {"internship_id": "203", "title": "Machine Learning Intern", "description": "Build and train machine learning models for predictions", "required_skills": "Python, Machine Learning, NLP"},
    {"internship_id": "204", "title": "Cloud Engineer Intern", "description": "Manage cloud infrastructure, databases, and automation", "required_skills": "Cloud Computing, SQL, AWS"},
    {"internship_id": "205", "title": "Backend Developer Intern", "description": "Work on APIs, databases and server-side applications", "required_skills": "Java, Spring Boot, MySQL"},
    {"internship_id": "206", "title": "Full Stack Developer Intern", "description": "Develop both frontend and backend of web applications", "required_skills": "React, Node.js, MongoDB"},
    {"internship_id": "207", "title": "Business Analyst Intern", "description": "Analyze business data and create reports", "required_skills": "Excel, PowerBI, Statistics"},
    {"internship_id": "208", "title": "AI Research Intern", "description": "Conduct research in NLP and deep learning models", "required_skills": "Python, NLP, Deep Learning"},
    {"internship_id": "209", "title": "Mobile App Developer Intern", "description": "Develop Android mobile apps with modern tools", "required_skills": "Android, Kotlin, Firebase"},
    {"internship_id": "210", "title": "Cybersecurity Intern", "description": "Learn ethical hacking and security tools", "required_skills": "Cybersecurity, Networking, Linux"}
]

internships_df = pd.DataFrame(internships_data)

class ProfilePayload(BaseModel):
    skills: str = ""
    interests: str = ""

@app.post("/recommend/profile")
def recommend_by_profile(payload: ProfilePayload):
    profile_text = ((payload.skills or "") + " " + (payload.interests or "")).strip()
    if not profile_text:
        return {"status": "error", "message": "Please provide skills and/or interests"}

    # Build internship documents
    internship_docs = []
    for _, row in internships_df.iterrows():
        doc = f"{row['title']} {row['description']} {row['required_skills']}"
        internship_docs.append(simple_preprocess(doc))

    # Create TF-IDF vectors
    vectorizer = TfidfVectorizer()
    student_doc = simple_preprocess(profile_text)
    all_docs = [student_doc] + internship_docs
    tfidf_matrix = vectorizer.fit_transform(all_docs)

    # Calculate similarities
    student_vector = tfidf_matrix[0:1]
    internship_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(student_vector, internship_vectors).flatten()

    # Rank internships
    internships_df_copy = internships_df.copy()
    internships_df_copy["match_score"] = similarities
    ranked = internships_df_copy.sort_values(by="match_score", ascending=False).reset_index(drop=True)

    # Return top recommendations
    recommendations = []
    for _, row in ranked.head(5).iterrows():
        recommendations.append({
            "internship_id": row.get("internship_id"),
            "title": row.get("title"),
            "match_score": round(float(row.get("match_score", 0.0)), 4)
        })

    return {
        "status": "success",
        "recommendations": recommendations
    }

@app.get("/")
def root():
    return {"message": "AvsarSetu AI Recommendation API", "status": "running"}

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting AvsarSetu AI Recommendation API...")
    print("📍 API will be available at: http://localhost:8000")
    print("📚 Documentation at: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)