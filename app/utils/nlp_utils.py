import re
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from app import app

# Download NLTK data if not already present
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

def preprocess_text(text):
    """Basic text preprocessing for NLP tasks"""
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters and numbers
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    
    # Tokenize and remove stopwords
    stop_words = set(stopwords.words('english') + stopwords.words('french'))
    words = word_tokenize(text)
    words = [word for word in words if word not in stop_words and len(word) > 2]
    
    return " ".join(words)

def extract_keywords(text, n=5):
    """Extract top n keywords from text"""
    processed_text = preprocess_text(text)
    words = processed_text.split()
    word_counts = Counter(words)
    return [word for word, count in word_counts.most_common(n)]

def calculate_similarity(text1, text2):
    """Calculate simple text similarity (0-1)"""
    if not text1 or not text2:
        return 0.0
    
    set1 = set(preprocess_text(text1).split())
    set2 = set(preprocess_text(text2).split())
    
    if not set1 or not set2:
        return 0.0
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    return intersection / union

def detect_language(text):
    """Simple language detection (English/French)"""
    if not text:
        return None
    
    # Count common words for each language
    english_words = {'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i'}
    french_words = {'le', 'la', 'de', 'et', 'à', 'les', 'des', 'en', 'un', 'une'}
    
    words = set(word_tokenize(text.lower()))
    english_count = len(words & english_words)
    french_count = len(words & french_words)
    
    if english_count > french_count:
        return 'en'
    elif french_count > english_count:
        return 'fr'
    else:
        return None