#!/usr/bin/env python3
"""
Simple AvsarSetu Recommendation Demo
Bypasses NLTK dependencies for demonstration
"""

import pandas as pd
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import json

def simple_preprocess(text):
    """Simple text preprocessing without NLTK"""
    if text is None:
        text = ""
    text = str(text).lower()
    # Remove non-alphanumeric characters except spaces
    import re
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    # Simple tokenization and stopword removal
    tokens = text.split()
    stopwords = {'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
                'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
                'to', 'was', 'will', 'with', 'i', 'you', 'this', 'but', 'they', 'have'}
    tokens = [t for t in tokens if t not in stopwords and len(t) > 1]
    return " ".join(tokens)

def load_data(students_path, internships_path):
    """Load CSV data"""
    students_df = pd.read_csv(students_path, dtype=str).fillna("")
    internships_df = pd.read_csv(internships_path, dtype=str).fillna("")
    return students_df, internships_df

def build_student_document(row):
    """Create student profile text"""
    skills = str(row.get("skills", ""))
    interests = str(row.get("interests", ""))
    return f"{skills} {interests}".strip()

def build_internship_document(row):
    """Create internship text"""
    title = str(row.get("title", ""))
    description = str(row.get("description", ""))
    skills = str(row.get("required_skills", ""))
    return f"{title} {description} {skills}".strip()

def get_recommendations(student_id, students_df, internships_df, top_n=5):
    """Get internship recommendations for a student"""
    # Find student
    student_row = students_df[students_df["student_id"] == str(student_id)]
    if student_row.empty:
        return {"status": "error", "message": f"Student {student_id} not found"}

    # Build student profile
    student_doc = build_student_document(student_row.iloc[0])
    student_doc = simple_preprocess(student_doc)

    # Build internship documents
    internship_docs = []
    for _, row in internships_df.iterrows():
        doc = build_internship_document(row)
        internship_docs.append(simple_preprocess(doc))

    # Create TF-IDF vectors
    vectorizer = TfidfVectorizer()
    all_docs = [student_doc] + internship_docs
    tfidf_matrix = vectorizer.fit_transform(all_docs)

    # Calculate similarities
    student_vector = tfidf_matrix[0:1]
    internship_vectors = tfidf_matrix[1:]
    similarities = cosine_similarity(student_vector, internship_vectors).flatten()

    # Rank internships
    internships_df = internships_df.copy()
    internships_df["match_score"] = similarities
    ranked = internships_df.sort_values(by="match_score", ascending=False).reset_index(drop=True)

    # Return top recommendations
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

def main():
    print("🚀 AvsarSetu - Rural Internship Portal AI Demo")
    print("=" * 50)

    # Load data
    try:
        students_df, internships_df = load_data("students.csv", "internships.csv")
        print(f"✅ Loaded {len(students_df)} students and {len(internships_df)} internships")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return

    # Demo recommendations for each student
    for _, student in students_df.iterrows():
        student_id = student["student_id"]
        print(f"\n👨‍🎓 Student {student_id}: {student.get('skills', '')}")
        print(f"   Interests: {student.get('interests', '')}")

        result = get_recommendations(student_id, students_df, internships_df, top_n=3)

        if result["status"] == "success":
            print("   🎯 Top Recommendations:")
            for i, rec in enumerate(result["recommendations"], 1):
                print(f"      {i}. {rec['title']} (Match: {rec['match_score']:.2f})")
        else:
            print(f"   ❌ {result['message']}")

    print("\n🎉 Demo completed! The AI system successfully matched students with internships based on skills and interests.")

if __name__ == "__main__":
    main()