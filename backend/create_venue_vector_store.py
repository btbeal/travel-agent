import chromadb
from typing import Dict, Any, Optional
from reservation_tools import get_all_venues, search_venues
from sentence_transformers import SentenceTransformer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_venue(venue: Dict[str, Any]) -> tuple[str, str, Dict[str, Any]]:
    """
    Process a single venue into (id, document, metadata) format
    """
    venue_id = f"venue_{venue.get('id', {}).get('resy', 0)}"

    name = venue.get('name', '').strip()
    venue_type = venue.get('type', '')
    tagline = venue.get('tagline', '')
    description = venue.get('metadata', {}).get('description', '')
    keywords = venue.get('metadata', {}).get('keywords', [])
    
    text_parts = []
    if name: text_parts.append(f"Name: {name}")
    if venue_type: text_parts.append(f"Type: {venue_type}")
    if tagline: text_parts.append(f"Tagline: {tagline}")
    if description: text_parts.append(f"Description: {description}")
    if keywords: text_parts.append(f"Keywords: {', '.join(keywords)}")
    
    document = " | ".join(text_parts)
    
    location = venue.get('location', {})
    metadata = {
        'name': name,
        'type': venue_type,
        'description': description,
        'resy_id': venue.get('id', {}).get('resy') or 0,
        'locality': location.get('locality', '') or '',
        'neighborhood': location.get('neighborhood', '') or '',
        'address': location.get('address_1', '') or '',
        'price_range_id': venue.get('price_range_id') or 0,
        'rating': venue.get('rating') or 0.0,
        'latitude': location.get('latitude') or 0.0,
        'longitude': location.get('longitude') or 0.0,
    }
    
    return venue_id, document, metadata

def create_venue_vector_store(
    collection_path: str = "./venue_vector_db", 
    collection_name: str = "venues",
    embedding_model: str = "all-mpnet-base-v2"
):
    """
    Create ChromaDB vector store from venues data
    """
    logger.info("Fetching venues...")
    venues = get_all_venues()
    
    if not venues:
        logger.info("No venues found")
        return None
    
    logger.info(f"Processing {len(venues)} venues...")
    processed_venues = [process_venue(venue) for venue in venues]

    ids, documents, metadatas = zip(*processed_venues)

    logger.info("Creating embeddings...")
    model = SentenceTransformer(embedding_model)
    embeddings = model.encode(list(documents), batch_size=512, show_progress_bar=True).tolist()
    
    client = chromadb.PersistentClient(path=collection_path)
    
    try:
        collection = client.get_collection(name=collection_name)
        logger.info("Using existing collection")
    except:
        embedding_function = chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        collection = client.create_collection(
            name=collection_name,
            embedding_function=embedding_function
        )
        logger.info(f"Created new collection with {embedding_model}")
    
    batch_size = 1000
    for i in range(0, len(venues), batch_size):
        end_idx = min(i + batch_size, len(venues))
        
        collection.add(
            ids=list(ids[i:end_idx]),
            documents=list(documents[i:end_idx]),
            metadatas=list(metadatas[i:end_idx]),
            embeddings=embeddings[i:end_idx]
        )
        
        logger.info(f"Added batch {i//batch_size + 1} ({end_idx}/{len(venues)} venues)")
    
    logger.info(f"Vector store created with {collection.count()} venues")
    return collection

if __name__ == "__main__":
    create_venue_vector_store()