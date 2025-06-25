# ai_service.py
import os
import re
import time
import torch
from flask import current_app
from transformers import pipeline
from tenacity import retry, stop_after_attempt, wait_exponential
from huggingface_hub import InferenceClient
from langdetect import detect, LangDetectException
from deep_translator import GoogleTranslator

# sentence-transformers pour pertinence rapide
from sentence_transformers import SentenceTransformer, util


class AIService:
    summarizer = None
    similarity_model = None
    hf_client = None
    image_captioning = None
    intent_model = None
    intent_tokenizer = None

    @staticmethod
    def initialize():
        """Initialisation des modèles IA et du client Hugging Face."""
        try:
            device = 0 if torch.cuda.is_available() else -1

            # Résumé ultra-rapide
            AIService.summarizer = pipeline(
                "summarization",
                model="sshleifer/distilbart-cnn-12-6",
                device=device
            )
            current_app.logger.info("✅ Modèle summarization chargé.")

            # Pertinence avec sentence-transformers
            AIService.similarity_model = SentenceTransformer("paraphrase-MiniLM-L6-v2")
            current_app.logger.info("✅ Modèle similarité chargé.")

            # Captioning image (inchangé)
            try:
                AIService.image_captioning = pipeline(
                    "image-to-text",
                    model="Salesforce/blip-image-captioning-base",
                    device=device,
                    model_kwargs={"resume_download": True}
                )
                current_app.logger.info("✅ Modèle image-to-text chargé.")
            except Exception as e:
                current_app.logger.warning(f"⚠️ Image-to-text distant échoué : {e}")
                try:
                    AIService.image_captioning = pipeline("image-to-text", model="./models/blip-base", device=device)
                    current_app.logger.info("✅ Modèle local image-to-text chargé.")
                except Exception as ex:
                    current_app.logger.error(f"❌ Échec total image-to-text : {ex}")
                    AIService.image_captioning = None

            # Intent model (inchangé)
            if os.path.exists("./intent_model"):
                from transformers import CamembertForSequenceClassification, CamembertTokenizerFast
                AIService.intent_tokenizer = CamembertTokenizerFast.from_pretrained("./intent_model")
                AIService.intent_model = CamembertForSequenceClassification.from_pretrained("./intent_model")
                current_app.logger.info("✅ Modèle d’intention chargé.")

        except Exception as e:
            current_app.logger.error(f"❌ Erreur init modèles : {e}")

        # Client HF
        hf_token = os.getenv("HF_API_TOKEN")
        if hf_token:
            try:
                AIService.hf_client = InferenceClient(token=hf_token)
                current_app.logger.info("✅ Client Hugging Face initialisé.")
            except Exception as e:
                current_app.logger.error(f"❌ Erreur HF client : {e}")
        else:
            current_app.logger.warning("⚠️ Token HF_API_TOKEN manquant.")

    @staticmethod
    def comprehend_query(query):
        """Analyse sémantique de la requête utilisateur."""
        try:
            lang = detect(query)
        except LangDetectException:
            lang = "fr"
            current_app.logger.warning("Langue non détectée, fallback sur fr.")

        if lang not in ["fr", "en"]:
            try:
                query = GoogleTranslator(source=lang, target="en").translate(query)
                lang = "en"
                current_app.logger.info(f"🌍 Requête traduite automatiquement : {query}")
            except Exception as e:
                current_app.logger.warning(f"Traduction échouée : {e}")

        query_lower = query.lower()
        intent = "search"
        if query.strip().endswith("?") or query_lower.startswith(("what", "how", "why", "qu'est-ce", "comment", "pourquoi")):
            intent = "explanation"

        words = re.findall(r'\w+', query_lower)
        stopwords = {"the", "a", "an", "of", "and", "de", "le", "la", "les"}
        keywords = [w for w in words if w not in stopwords]

        return {
            "intent": intent,
            "keywords": keywords,
            "language": lang,
            "original_query": query
        }

    @staticmethod
    def describe_image(image_path):
        """Renvoie une description d’image via IA."""
        try:
            if not AIService.image_captioning:
                return "🟥 Captioning non disponible"
            description = AIService.image_captioning(image_path)
            if isinstance(description, list) and 'generated_text' in description[0]:
                return description[0]['generated_text']
            return "Description indisponible"
        except Exception as e:
            current_app.logger.error(f"Erreur image captioning : {e}")
            return "Description indisponible"

    @staticmethod
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=4))
    def enrich_search_results(query, results):
        """Ajoute résumé IA, score de pertinence et topics aux résultats."""
        if not results or not AIService.summarizer or not AIService.similarity_model:
            return []

        enriched = []
        for result in results:
            try:
                context = result.get('snippet', '')[:512]
                if not context:
                    enriched.append({**result, 'ai_summary': "Résumé indisponible", 'relevance_score': 5, 'topics': [], 'enriched': False})
                    continue

                # Résumé ultra-rapide
                summary = AIService.summarizer(context, max_length=50, min_length=10, do_sample=False)[0]['summary_text']

                # Pertinence : cosine similarity query/context
                score = util.cos_sim(
                    AIService.similarity_model.encode(query, convert_to_tensor=True),
                    AIService.similarity_model.encode(context, convert_to_tensor=True)
                ).item()
                score = round(score * 10)  # Scale to 0-10

                words = re.findall(r'\w+', context.lower())
                stopwords = {"le", "la", "les", "the", "and", "de"}
                topics = sorted(set([w for w in words if w not in stopwords]), key=words.count, reverse=True)[:5]

                enriched.append({**result, 'ai_summary': summary, 'relevance_score': score, 'topics': topics, 'enriched': True})
                time.sleep(0.2)

            except Exception as e:
                current_app.logger.warning(f"[AIService] Erreur enrichissement : {e}")
                enriched.append({**result, 'ai_summary': "Résumé indisponible", 'relevance_score': 5, 'topics': [], 'enriched': False})

        return sorted(enriched, key=lambda x: x['relevance_score'], reverse=True)

    @staticmethod
    def generate_images(prompt, limit=1):
        """Génère des images IA via Hugging Face."""
        if not AIService.hf_client:
            current_app.logger.error("❌ Client Hugging Face non initialisé.")
            return []

        image_urls = []
        for i in range(limit):
            try:
                image = AIService.hf_client.text_to_image(prompt, model="stabilityai/stable-diffusion-2")
                filename = f"generated_{re.sub(r'[^a-zA-Z0-9]', '_', prompt)}_{i}.png"
                filepath = os.path.join("static", "generated", filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                image.save(filepath)
                image_urls.append(f"/static/generated/{filename}")
                time.sleep(0.3)
            except Exception as e:
                current_app.logger.error(f"❌ Erreur génération image : {e}")
        return image_urls

    @staticmethod
    def train_intent_recognition(train_data):
        """Entraîne un modèle d’intention personnalisé."""
        try:
            from transformers import CamembertForSequenceClassification, CamembertTokenizerFast, Trainer, TrainingArguments

            tokenizer = CamembertTokenizerFast.from_pretrained("illuin/camembert-base-fquad")
            labels = list(set(d['intent'] for d in train_data))
            label_map = {intent: i for i, intent in enumerate(labels)}
            model = CamembertForSequenceClassification.from_pretrained("illuin/camembert-base-fquad", num_labels=len(labels))

            encodings = tokenizer([d['text'] for d in train_data], truncation=True, padding=True, max_length=128)
            dataset = torch.utils.data.TensorDataset(
                torch.tensor(encodings['input_ids']),
                torch.tensor(encodings['attention_mask']),
                torch.tensor([label_map[d['intent']] for d in train_data])
            )

            args = TrainingArguments(output_dir="./intent_model", num_train_epochs=3, per_device_train_batch_size=8, logging_dir="./logs")
            trainer = Trainer(model=model, args=args, train_dataset=dataset)
            trainer.train()
            model.save_pretrained("./intent_model")
            tokenizer.save_pretrained("./intent_model")

            current_app.logger.info("✅ Modèle d’intention entraîné avec succès.")
            return True
        except Exception as e:
            current_app.logger.error(f"Erreur entraînement modèle intention : {e}")
            return False

    @staticmethod
    def predict_intent(text):
        """Prédit l’intention d’une requête utilisateur."""
        try:
            if not AIService.intent_model or not AIService.intent_tokenizer:
                return "Modèle non chargé"
            tokens = AIService.intent_tokenizer(text, return_tensors="pt", truncation=True, padding=True)
            output = AIService.intent_model(**tokens)
            pred = output.logits.argmax().item()
            return f"Intent #{pred}"
        except Exception as e:
            current_app.logger.error(f"Erreur prédiction intention : {e}")
            return "Indéterminé"

    @staticmethod
    def analyze_input(input_data):
        """Analyse auto (texte ou image)."""
        if isinstance(input_data, str) and os.path.exists(input_data) and input_data.lower().endswith(('.png', '.jpg', '.jpeg')):
            return AIService.describe_image(input_data)
        return AIService.comprehend_query(input_data)
