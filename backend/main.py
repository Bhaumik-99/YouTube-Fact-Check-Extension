"""
FastAPI backend for YouTube fact-checking extension
Handles audio processing, claim extraction, and fact verification
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import tempfile
import os
import logging
from typing import List, Dict, Any
import uvicorn

from claim_extractor import ClaimExtractor
from fact_checker import FactChecker
from config import Config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="YouTube Fact Checker API",
    description="Backend service for real-time YouTube fact-checking",
    version="1.0.0"
)

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
config = Config()
claim_extractor = ClaimExtractor(config)
fact_checker = FactChecker(config)

# In-memory storage for processed claims (use database in production)
video_claims: Dict[str, List[Dict[str, Any]]] = {}

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "YouTube Fact Checker API is running"}

@app.post("/upload-audio")
async def upload_audio(
    audio: UploadFile = File(...),
    video_id: str = Form(...),
    timestamp: float = Form(...),
    duration: float = Form(...),
    api_key: str = Form(...)
):
    """
    Process audio chunk and return fact-checked claims
    
    Args:
        audio: Audio file (WebM format)
        video_id: YouTube video ID
        timestamp: Start timestamp in video (seconds)
        duration: Duration of audio chunk (seconds)
        api_key: API key for external services
        
    Returns:
        JSON response with detected claims and their fact-check results
    """
    try:
        logger.info(f"Processing audio for video {video_id} at {timestamp}s")
        
        # Validate API key (basic validation)
        if not api_key or len(api_key) < 10:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        # Save uploaded audio to temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.webm') as temp_audio:
            content = await audio.read()
            temp_audio.write(content)
            temp_audio_path = temp_audio.name
        
        try:
            # Step 1: Convert audio to text using Whisper
            logger.info("Converting audio to text...")
            transcript = await claim_extractor.audio_to_text(temp_audio_path, api_key)
            
            if not transcript or len(transcript.strip()) < 10:
                logger.info("No substantial transcript found")
                return JSONResponse({"claims": []})
            
            logger.info(f"Transcript: {transcript[:100]}...")
            
            # Step 2: Extract factual claims from transcript
            logger.info("Extracting claims...")
            claims = await claim_extractor.extract_claims(transcript, timestamp)
            
            if not claims:
                logger.info("No factual claims detected")
                return JSONResponse({"claims": []})
            
            logger.info(f"Found {len(claims)} claims")
            
            # Step 3: Fact-check each claim
            verified_claims = []
            for claim_data in claims:
                logger.info(f"Fact-checking: {claim_data['claim']}")
                
                verdict = await fact_checker.check_claim(claim_data['claim'], api_key)
                
                verified_claim = {
                    "claim": claim_data['claim'],
                    "timestamp": claim_data['timestamp'],
                    "verdict": verdict['verdict'],
                    "confidence": verdict['confidence'],
                    "sources": verdict['sources']
                }
                
                verified_claims.append(verified_claim)
            
            # Store results for later retrieval
            if video_id not in video_claims:
                video_claims[video_id] = []
            video_claims[video_id].extend(verified_claims)
            
            logger.info(f"Processed {len(verified_claims)} verified claims")
            
            return JSONResponse({
                "claims": verified_claims,
                "transcript": transcript
            })
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
                
    except Exception as e:
        logger.error(f"Error processing audio: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Processing error: {str(e)}")

@app.get("/get-verdicts/{video_id}")
async def get_verdicts(video_id: str):
    """
    Retrieve all processed claims for a video
    
    Args:
        video_id: YouTube video ID
        
    Returns:
        JSON response with all claims processed so far
    """
    try:
        claims = video_claims.get(video_id, [])
        return JSONResponse({
            "video_id": video_id,
            "claims": claims,
            "total_claims": len(claims)
        })
    except Exception as e:
        logger.error(f"Error retrieving verdicts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/clear-verdicts/{video_id}")
async def clear_verdicts(video_id: str):
    """Clear all stored claims for a video"""
    try:
        if video_id in video_claims:
            del video_claims[video_id]
        return JSONResponse({"message": f"Cleared claims for video {video_id}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )