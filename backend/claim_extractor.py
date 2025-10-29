import json 
import re    
import openai  
from typing import List, Dict, Any     
import logging   
import asyncio     
         
logger = logging.getLogger(__name__)
     
class ClaimExtractor:
    """
    A class to handle audio transcription using OpenAI Whisper API.
    """

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    async def audio_to_text(self, audio_path: str, api_key: str, language: Optional[str] = "en") -> str:
        """
        Convert an audio file to text using the OpenAI Whisper API.

        Args:
            audio_path (str): Path to the audio file.
            api_key (str): OpenAI API key.
            language (Optional[str]): Language of the audio. Defaults to 'en'.

        Returns:
            str: Transcribed text from the audio.
        """
        openai.api_key = api_key

        try:
            self.logger.info(f"Starting transcription for: {audio_path}")
            
            # Use asyncio.to_thread for non-blocking file I/O
            def transcribe_audio():
                with open(audio_path, "rb") as audio_file:
                    return openai.Audio.transcribe(
                        model="whisper-1",
                        file=audio_file,
                        language=language
                    )

            response = await asyncio.to_thread(transcribe_audio)
            transcript = response.text.strip() if hasattr(response, "text") else response["text"].strip()

            self.logger.info("Transcription successful.")
            return transcript

        except FileNotFoundError:
            self.logger.error(f"Audio file not found: {audio_path}")
            raise

        except openai.error.OpenAIError as e:
            self.logger.error(f"OpenAI API error: {e}")
            raise

        except Exception as e:
            self.logger.exception("Unexpected error during transcription.")
            raise
            
        except Exception as e:
            logger.error(f"Error in audio transcription: {str(e)}")
            # Fallback to dummy transcript for testing
            return "This is a sample transcript for testing purposes."
    
    async def extract_claims(self, transcript: str, base_timestamp: float) -> List[Dict[str, Any]]:
        """
        Extract factual claims from transcript using LLM
        
        Args:
            transcript: Text transcript
            base_timestamp: Base timestamp for the audio chunk
            
        Returns:
            List of detected claims with timestamps
        """
        try:
            # For MVP, use a simple pattern-based approach
            # In production, use a more sophisticated LLM-based method
            
            claims = []
            sentences = self._split_into_sentences(transcript)
            
            for i, sentence in enumerate(sentences):
                if self._is_factual_claim(sentence):
                    # Estimate timestamp within the chunk
                    sentence_timestamp = base_timestamp + (i * 2.0)  # Rough estimate
                    
                    claims.append({
                        "claim": sentence.strip(),
                        "timestamp": sentence_timestamp
                    })
            
            return claims
            
        except Exception as e:
            logger.error(f"Error extracting claims: {str(e)}")
            return []
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    
    def _is_factual_claim(self, sentence: str) -> bool:
        """
        Determine if a sentence contains a factual claim
        Simple heuristic-based approach for MVP
        """
        sentence_lower = sentence.lower()
        
        # Skip obvious opinions and questions
        opinion_words = ['i think', 'i believe', 'in my opinion', 'maybe', 'perhaps']
        if any(word in sentence_lower for word in opinion_words):
            return False
        
        if sentence.strip().endswith('?'):
            return False
        
        # Look for factual indicators
        factual_patterns = [
            r'\b\d+\b',  # Contains numbers
            r'\b(is|are|was|were|has|have|will|can|cannot)\b',  # Factual verbs
            r'\b(percent|million|billion|degrees|miles|kilometers)\b',  # Units
            r'\b(studies show|research indicates|data shows|according to)\b',  # Citations
        ]
        
        return any(re.search(pattern, sentence_lower) for pattern in factual_patterns)

    async def extract_claims_with_llm(self, transcript: str, api_key: str, base_timestamp: float) -> List[Dict[str, Any]]:
        """
        Extract claims using LLM (OpenAI GPT) - more accurate but requires API calls
        This is an enhanced version for production use
        """
        try:
            openai.api_key = api_key
            
            prompt = f"""
            Analyze the following transcript and extract factual claims that can be fact-checked.
            Ignore opinions, questions, and subjective statements.
            Return ONLY a valid JSON array with this exact format:
            
            [
                {{"claim": "specific factual statement", "start_time": 0.0, "end_time": 2.5}},
                {{"claim": "another factual statement", "start_time": 3.0, "end_time": 6.0}}
            ]
            
            Transcript: "{transcript}"
            
            JSON array of factual claims:
            """
            
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert at identifying factual claims that can be verified. Extract only objective, verifiable statements."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            
            claims_text = response.choices[0].message.content.strip()
            
            # Parse JSON response
            try:
                claims_data = json.loads(claims_text)
                
                # Convert to our format with absolute timestamps
                claims = []
                for claim_info in claims_data:
                    claims.append({
                        "claim": claim_info["claim"],
                        "timestamp": base_timestamp + claim_info.get("start_time", 0)
                    })
                
                return claims
                
            except json.JSONDecodeError:
                logger.warning("LLM returned invalid JSON, falling back to heuristic method")
                return await self.extract_claims(transcript, base_timestamp)
                
        except Exception as e:
            logger.error(f"Error in LLM claim extraction: {str(e)}")
            return await self.extract_claims(transcript, base_timestamp)
