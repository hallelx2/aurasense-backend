# Aurasense Backend Implementation Plan - Alternative Architecture (4 Days)

## 🎯 Project Overview
Building a voice-first, culturally-aware food ordering and travel companion with multi-agent architecture using a **cloud bucket-based audio processing flow** for the Raise Your Hack hackathon (4-day sprint).

## 📅 4-Day Sprint Plan

### **Day 1: Foundation & Core Infrastructure**
- [ ] Backend architecture setup
- [ ] Database initialization
- [ ] Cloud storage setup (AWS S3/Google Cloud Storage)
- [ ] Basic agent framework
- [ ] Audio upload/download pipeline
- [ ] Authentication system

### **Day 2: Agent Development & Audio Processing**
- [ ] Implement all 6 specialized agents
- [ ] Restaurant data collection pipeline
- [ ] Audio processing workflow
- [ ] Real-time MCP integrations

### **Day 3: Intelligence & Integration**
- [ ] Cultural adaptation engine
- [ ] Health-aware recommendations
- [ ] Agent orchestration
- [ ] API integrations

### **Day 4: Polish & Demo Preparation**
- [ ] End-to-end testing
- [ ] Demo scenarios
- [ ] Performance optimization
- [ ] Deployment

---

## 🏗️ Alternative Backend Architecture

### **Technology Stack**
```text
Backend Framework: FastAPI (Python)
Database: Neo4j (Knowledge Graph) + Redis (Caching)
Temporal Memory: Graphiti Knowledge Graph
Agent Framework: LangGraph
LLM Provider: Groq (Llama models)
Voice Processing: Groq Whisper
Audio Storage: AWS S3 / Google Cloud Storage
Real-time Communication: HTTP REST API + Polling/WebHooks
Authentication: Custom voice-based system
Deployment: Docker + Cloud provider
```

### **Audio Processing Flow Architecture**
```text
Frontend Audio Capture → Cloud Bucket Upload → Backend Download → Agent Processing → Response
```

### **Project Structure**
```text
aurasense-backend/
├── app/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── onboarding_agent.py
│   │   ├── auth_agent.py
│   │   ├── food_agent.py
│   │   ├── travel_agent.py
│   │   ├── social_agent.py
│   │   └── profile_agent.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── cache.py
│   │   └── security.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── audio_service.py          # NEW: Audio upload/download
│   │   ├── cloud_storage_service.py  # NEW: S3/GCS integration
│   │   ├── voice_service.py
│   │   ├── cultural_service.py
│   │   ├── health_service.py
│   │   └── mcp_service.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── restaurant.py
│   │   ├── hotel.py
│   │   ├── audio_session.py          # NEW: Audio session tracking
│   │   └── session.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── audio_endpoints.py        # NEW: Audio upload/process endpoints
│   │   ├── voice.py
│   │   └── health.py
│   ├── data/
│   │   ├── __init__.py
│   │   ├── collectors/
│   │   ├── enrichers/
│   │   └── schemas/
│   └── main.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 🎤 Audio Processing Pipeline (Alternative Architecture)

### **Complete Audio Flow**
```python
# Step-by-step audio processing workflow
class AudioProcessingFlow:
    def __init__(self):
        self.cloud_storage = CloudStorageService()
        self.voice_service = VoiceService()
        self.agent_orchestrator = AgentOrchestrator()

    async def process_audio_request(self, audio_url: str, user_id: str, session_id: str) -> Dict:
        """
        Complete audio processing pipeline
        Frontend → Cloud Bucket → Backend → Agent → Response
        """

        # Step 1: Download audio from cloud bucket
        audio_data = await self.cloud_storage.download_audio(audio_url)

        # Step 2: Transcribe audio using Groq Whisper
        transcription = await self.voice_service.transcribe_audio(audio_data)

        # Step 3: Extract cultural context from voice patterns
        voice_profile = await self.voice_service.analyze_voice_patterns(audio_data)

        # Step 4: Route to appropriate agent based on content and user context
        agent_response = await self.agent_orchestrator.process_request(
            user_input=transcription,
            user_id=user_id,
            voice_profile=voice_profile,
            session_id=session_id
        )

        # Step 5: Generate voice response
        response_audio = await self.voice_service.text_to_speech(
            text=agent_response['text'],
            voice_style=voice_profile['cultural_voice_preference']
        )

        # Step 6: Upload response audio to cloud bucket
        response_audio_url = await self.cloud_storage.upload_audio(
            audio_data=response_audio,
            file_name=f"response_{session_id}_{timestamp}.wav"
        )

        return {
            "transcription": transcription,
            "response_text": agent_response['text'],
            "response_audio_url": response_audio_url,
            "agent_used": agent_response['agent'],
            "cultural_context": voice_profile,
            "session_id": session_id
        }
```

### **Cloud Storage Service Implementation**
```python
# Cloud storage service for audio files
import boto3
from google.cloud import storage
import aiofiles
import tempfile
import uuid
from datetime import datetime, timedelta

class CloudStorageService:
    def __init__(self):
        # AWS S3 Configuration
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        self.bucket_name = settings.AUDIO_BUCKET_NAME

        # Google Cloud Storage (alternative)
        # self.gcs_client = storage.Client()
        # self.bucket = self.gcs_client.bucket(settings.GCS_BUCKET_NAME)

    async def upload_audio(self, audio_data: bytes, file_name: str = None) -> str:
        """Upload audio data to cloud storage and return public URL"""
        if not file_name:
            file_name = f"audio_{uuid.uuid4()}_{int(datetime.now().timestamp())}.wav"

        try:
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=f"audio/{file_name}",
                Body=audio_data,
                ContentType="audio/wav",
                # Set expiration for temporary files (24 hours)
                Expires=datetime.now() + timedelta(hours=24)
            )

            # Generate presigned URL for access
            audio_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': f"audio/{file_name}"},
                ExpiresIn=86400  # 24 hours
            )

            return audio_url

        except Exception as e:
            logger.error(f"Failed to upload audio: {str(e)}")
            raise HTTPException(status_code=500, detail="Audio upload failed")

    async def download_audio(self, audio_url: str) -> bytes:
        """Download audio from cloud storage URL"""
        try:
            # Extract bucket and key from URL
            bucket, key = self._parse_s3_url(audio_url)

            # Download from S3
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            audio_data = response['Body'].read()

            return audio_data

        except Exception as e:
            logger.error(f"Failed to download audio: {str(e)}")
            raise HTTPException(status_code=500, detail="Audio download failed")

    def _parse_s3_url(self, url: str) -> tuple:
        """Parse S3 URL to extract bucket and key"""
        # Handle both presigned URLs and direct S3 URLs
        if 'amazonaws.com' in url:
            parts = url.split('/')
            bucket = parts[2].split('.')[0]
            key = '/'.join(parts[3:]).split('?')[0]
            return bucket, key
        else:
            raise ValueError("Invalid S3 URL format")

    async def cleanup_old_files(self):
        """Clean up expired audio files (run as background task)"""
        try:
            # List objects older than 24 hours
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix="audio/"
            )

            current_time = datetime.now()
            for obj in response.get('Contents', []):
                if (current_time - obj['LastModified'].replace(tzinfo=None)).hours > 24:
                    self.s3_client.delete_object(
                        Bucket=self.bucket_name,
                        Key=obj['Key']
                    )

        except Exception as e:
            logger.error(f"Cleanup failed: {str(e)}")
```

### **Audio Session Management**
```python
# Audio session tracking and management
from sqlalchemy import Column, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
import uuid
from datetime import datetime

class AudioSession(Base):
    __tablename__ = "audio_sessions"

    session_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False)
    input_audio_url = Column(String, nullable=False)
    output_audio_url = Column(String, nullable=True)
    transcription = Column(Text, nullable=True)
    agent_response = Column(Text, nullable=True)
    agent_used = Column(String, nullable=True)
    cultural_context = Column(Text, nullable=True)  # JSON string
    processing_status = Column(String, default="pending")  # pending, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

class AudioSessionService:
    def __init__(self, db_session):
        self.db = db_session

    async def create_session(self, user_id: str, input_audio_url: str) -> str:
        """Create new audio processing session"""
        session = AudioSession(
            user_id=user_id,
            input_audio_url=input_audio_url,
            processing_status="pending"
        )
        self.db.add(session)
        await self.db.commit()
        return session.session_id

    async def update_session_progress(self, session_id: str, status: str, **kwargs):
        """Update session with processing progress"""
        session = await self.db.query(AudioSession).filter(
            AudioSession.session_id == session_id
        ).first()

        if session:
            session.processing_status = status
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)

            if status == "completed":
                session.completed_at = datetime.utcnow()

            await self.db.commit()

    async def get_session_status(self, session_id: str) -> Dict:
        """Get current session status and results"""
        session = await self.db.query(AudioSession).filter(
            AudioSession.session_id == session_id
        ).first()

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return {
            "session_id": session.session_id,
            "status": session.processing_status,
            "transcription": session.transcription,
            "response_text": session.agent_response,
            "response_audio_url": session.output_audio_url,
            "agent_used": session.agent_used,
            "created_at": session.created_at,
            "completed_at": session.completed_at,
            "error_message": session.error_message
        }
```

---

## 🌐 API Endpoints (Alternative Architecture)

### **Audio Processing Endpoints**
```python
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel
import asyncio

app = FastAPI()

class AudioProcessRequest(BaseModel):
    audio_url: str
    user_id: str
    session_context: Dict = {}

class AudioProcessResponse(BaseModel):
    session_id: str
    status: str
    message: str

class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    transcription: str = None
    response_text: str = None
    response_audio_url: str = None
    agent_used: str = None
    error_message: str = None

@app.post("/api/audio/process", response_model=AudioProcessResponse)
async def process_audio(
    request: AudioProcessRequest,
    background_tasks: BackgroundTasks,
    audio_service: AudioSessionService = Depends(get_audio_service)
):
    """
    Initiate audio processing
    Frontend uploads audio to bucket, then calls this endpoint with the URL
    """
    try:
        # Create new session
        session_id = await audio_service.create_session(
            user_id=request.user_id,
            input_audio_url=request.audio_url
        )

        # Start background processing
        background_tasks.add_task(
            process_audio_background,
            session_id=session_id,
            audio_url=request.audio_url,
            user_id=request.user_id,
            context=request.session_context
        )

        return AudioProcessResponse(
            session_id=session_id,
            status="processing",
            message="Audio processing started"
        )

    except Exception as e:
        logger.error(f"Failed to initiate audio processing: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start processing")

@app.get("/api/audio/status/{session_id}", response_model=SessionStatusResponse)
async def get_processing_status(
    session_id: str,
    audio_service: AudioSessionService = Depends(get_audio_service)
):
    """
    Get current status of audio processing session
    Frontend polls this endpoint to check progress
    """
    try:
        session_data = await audio_service.get_session_status(session_id)
        return SessionStatusResponse(**session_data)

    except Exception as e:
        logger.error(f"Failed to get session status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get status")

@app.post("/api/audio/upload-presigned")
async def get_upload_presigned_url(
    file_name: str,
    content_type: str = "audio/wav",
    cloud_storage: CloudStorageService = Depends(get_cloud_storage)
):
    """
    Generate presigned URL for frontend to upload audio directly to cloud storage
    """
    try:
        presigned_data = await cloud_storage.generate_presigned_upload_url(
            file_name=file_name,
            content_type=content_type
        )

        return {
            "upload_url": presigned_data["url"],
            "fields": presigned_data["fields"],
            "final_url": presigned_data["final_url"]
        }

    except Exception as e:
        logger.error(f"Failed to generate presigned URL: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")

async def process_audio_background(
    session_id: str,
    audio_url: str,
    user_id: str,
    context: Dict
):
    """
    Background task for processing audio
    """
    audio_service = AudioSessionService()
    audio_processor = AudioProcessingFlow()

    try:
        # Update status to processing
        await audio_service.update_session_progress(session_id, "processing")

        # Process the audio
        result = await audio_processor.process_audio_request(
            audio_url=audio_url,
            user_id=user_id,
            session_id=session_id
        )

        # Update session with results
        await audio_service.update_session_progress(
            session_id=session_id,
            status="completed",
            transcription=result["transcription"],
            agent_response=result["response_text"],
            output_audio_url=result["response_audio_url"],
            agent_used=result["agent_used"],
            cultural_context=json.dumps(result["cultural_context"])
        )

    except Exception as e:
        logger.error(f"Audio processing failed for session {session_id}: {str(e)}")
        await audio_service.update_session_progress(
            session_id=session_id,
            status="failed",
            error_message=str(e)
        )
```

---

## 🔄 Frontend Integration Pattern

### **Frontend Audio Upload Flow**
```javascript
// Frontend JavaScript for audio upload and processing
class AurasenseAudioClient {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
        this.mediaRecorder = null;
        this.audioChunks = [];
    }

    async startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                this.audioChunks.push(event.data);
            };

            this.mediaRecorder.start();
            return true;
        } catch (error) {
            console.error('Failed to start recording:', error);
            return false;
        }
    }

    async stopRecording() {
        return new Promise((resolve) => {
            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                resolve(audioBlob);
            };
            this.mediaRecorder.stop();
        });
    }

    async uploadAudioAndProcess(audioBlob, userId, sessionContext = {}) {
        try {
            // Step 1: Get presigned upload URL
            const uploadUrlResponse = await fetch(`${this.apiBaseUrl}/api/audio/upload-presigned`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_name: `audio_${Date.now()}.wav`,
                    content_type: 'audio/wav'
                })
            });

            const uploadData = await uploadUrlResponse.json();

            // Step 2: Upload audio directly to cloud storage
            const formData = new FormData();
            Object.entries(uploadData.fields).forEach(([key, value]) => {
                formData.append(key, value);
            });
            formData.append('file', audioBlob);

            await fetch(uploadData.upload_url, {
                method: 'POST',
                body: formData
            });

            // Step 3: Initiate backend processing
            const processResponse = await fetch(`${this.apiBaseUrl}/api/audio/process`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    audio_url: uploadData.final_url,
                    user_id: userId,
                    session_context: sessionContext
                })
            });

            const processData = await processResponse.json();

            // Step 4: Poll for results
            return await this.pollForResults(processData.session_id);

        } catch (error) {
            console.error('Audio processing failed:', error);
            throw error;
        }
    }

    async pollForResults(sessionId, maxAttempts = 30, interval = 2000) {
        for (let attempt = 0; attempt < maxAttempts; attempt++) {
            try {
                const response = await fetch(`${this.apiBaseUrl}/api/audio/status/${sessionId}`);
                const data = await response.json();

                if (data.status === 'completed') {
                    return data;
                } else if (data.status === 'failed') {
                    throw new Error(data.error_message || 'Processing failed');
                }

                // Wait before next poll
                await new Promise(resolve => setTimeout(resolve, interval));

            } catch (error) {
                console.error('Polling error:', error);
                if (attempt === maxAttempts - 1) throw error;
            }
        }

        throw new Error('Processing timeout');
    }

    async playAudioResponse(audioUrl) {
        const audio = new Audio(audioUrl);
        await audio.play();
    }
}

// Usage example
const audioClient = new AurasenseAudioClient('https://api.aurasense.com');

async function handleVoiceInteraction() {
    try {
        // Start recording
        await audioClient.startRecording();

        // Show recording UI
        document.getElementById('recordingIndicator').style.display = 'block';

        // Stop recording after user action (button release, etc.)
        const audioBlob = await audioClient.stopRecording();

        // Show processing UI
        document.getElementById('recordingIndicator').style.display = 'none';
        document.getElementById('processingIndicator').style.display = 'block';

        // Process audio
        const result = await audioClient.uploadAudioAndProcess(
            audioBlob,
            'user_123',
            { context: 'food_ordering' }
        );

        // Display results
        document.getElementById('transcription').textContent = result.transcription;
        document.getElementById('response').textContent = result.response_text;

        // Play audio response
        if (result.response_audio_url) {
            await audioClient.playAudioResponse(result.response_audio_url);
        }

        // Hide processing UI
        document.getElementById('processingIndicator').style.display = 'none';

    } catch (error) {
        console.error('Voice interaction failed:', error);
        // Handle error UI
    }
}
```

---

## ⚡ Performance Optimizations

### **Caching Strategy for Audio Processing**
```python
# Redis caching for audio processing results
class AudioCacheService:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.cache_ttl = 3600  # 1 hour

    async def cache_transcription(self, audio_hash: str, transcription: str):
        """Cache transcription results to avoid re-processing identical audio"""
        cache_key = f"transcription:{audio_hash}"
        await self.redis.setex(cache_key, self.cache_ttl, transcription)

    async def get_cached_transcription(self, audio_hash: str) -> str:
        """Get cached transcription if available"""
        cache_key = f"transcription:{audio_hash}"
        return await self.redis.get(cache_key)

    async def cache_voice_profile(self, audio_hash: str, voice_profile: Dict):
        """Cache voice analysis results"""
        cache_key = f"voice_profile:{audio_hash}"
        await self.redis.setex(cache_key, self.cache_ttl, json.dumps(voice_profile))

    async def get_cached_voice_profile(self, audio_hash: str) -> Dict:
        """Get cached voice profile if available"""
        cache_key = f"voice_profile:{audio_hash}"
        cached_data = await self.redis.get(cache_key)
        return json.loads(cached_data) if cached_data else None

def calculate_audio_hash(audio_data: bytes) -> str:
    """Calculate hash of audio data for caching"""
    return hashlib.md5(audio_data).hexdigest()
```

### **Parallel Processing Pipeline**
```python
# Parallel processing for better performance
import asyncio
from concurrent.futures import ThreadPoolExecutor

class OptimizedAudioProcessor:
    def __init__(self):
        self.cache_service = AudioCacheService()
        self.thread_pool = ThreadPoolExecutor(max_workers=4)

    async def process_audio_optimized(self, audio_url: str, user_id: str, session_id: str) -> Dict:
        """Optimized audio processing with caching and parallel execution"""

        # Download audio
        audio_data = await self.cloud_storage.download_audio(audio_url)
        audio_hash = calculate_audio_hash(audio_data)

        # Check cache for previous processing
        cached_transcription = await self.cache_service.get_cached_transcription(audio_hash)
        cached_voice_profile = await self.cache_service.get_cached_voice_profile(audio_hash)

        # Parallel processing tasks
        tasks = []

        # Transcription task
        if cached_transcription:
            transcription_task = asyncio.create_task(self._return_cached(cached_transcription))
        else:
            transcription_task = asyncio.create_task(self.voice_service.transcribe_audio(audio_data))
        tasks.append(transcription_task)

        # Voice analysis task
        if cached_voice_profile:
            voice_analysis_task = asyncio.create_task(self._return_cached(cached_voice_profile))
        else:
            voice_analysis_task = asyncio.create_task(self.voice_service.analyze_voice_patterns(audio_data))
        tasks.append(voice_analysis_task)

        # User context task (can run in parallel)
        user_context_task = asyncio.create_task(self.get_user_context(user_id))
        tasks.append(user_context_task)

        # Wait for all parallel tasks
        transcription, voice_profile, user_context = await asyncio.gather(*tasks)

        # Cache results if they were newly computed
        if not cached_transcription:
            await self.cache_service.cache_transcription(audio_hash, transcription)
        if not cached_voice_profile:
            await self.cache_service.cache_voice_profile(audio_hash, voice_profile)

        # Process with agent (sequential, depends on above results)
        agent_response = await self.agent_orchestrator.process_request(
            user_input=transcription,
            user_id=user_id,
            voice_profile=voice_profile,
            user_context=user_context,
            session_id=session_id
        )

        # Generate response audio (can be done in parallel with other tasks)
        response_audio_task = asyncio.create_task(
            self.voice_service.text_to_speech(
                text=agent_response['text'],
                voice_style=voice_profile['cultural_voice_preference']
            )
        )

        # Upload response audio to cloud
        response_audio = await response_audio_task
        response_audio_url = await self.cloud_storage.upload_audio(
            audio_data=response_audio,
            file_name=f"response_{session_id}_{int(time.time())}.wav"
        )

        return {
            "transcription": transcription,
            "response_text": agent_response['text'],
            "response_audio_url": response_audio_url,
            "agent_used": agent_response['agent'],
            "cultural_context": voice_profile,
            "session_id": session_id,
            "processing_time": time.time() - start_time
        }
```

---

## 🔧 Configuration & Environment Setup

### **Environment Variables for Alternative Architecture**
```python
# Additional environment variables for cloud storage
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Existing settings...
    GROQ_API_KEY: str
    GOOGLE_PLACES_API_KEY: str
    NEO4J_URI: str
    REDIS_URL: str

    # Cloud Storage Settings
    CLOUD_STORAGE_PROVIDER: str = "aws"  # aws, gcp, azure

    # AWS S3 Settings
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"
    AUDIO_BUCKET_NAME: str = "aurasense-audio-files"

    # Google Cloud Storage (alternative)
    GCP_PROJECT_ID: str = ""
    GCP_CREDENTIALS_PATH: str = ""
    GCS_BUCKET_NAME: str = "aurasense-audio-gcs"

    # Audio Processing Settings
    MAX_AUDIO_FILE_SIZE_MB: int = 10
    AUDIO_PROCESSING_TIMEOUT: int = 30  # seconds
    CACHE_AUDIO_RESULTS: bool = True
    CLEANUP_AUDIO_FILES_HOURS: int = 24

    class Config:
        env_file = ".env"

settings = Settings()
```

### **Docker Configuration for Alternative Architecture**
```dockerfile
# Dockerfile with cloud storage dependencies
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directories for temporary files
RUN mkdir -p /tmp/audio_processing

# Set environment variables
ENV PYTHONPATH=/app
ENV TEMP_AUDIO_DIR=/tmp/audio_processing

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```yaml
# docker-compose.yml with cloud storage
version: '3.8'

services:
  aurasense-backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AUDIO_BUCKET_NAME=${AUDIO_BUCKET_NAME}
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379
    depends_on:
      - neo4j
      - redis
    volumes:
      - /tmp/audio_processing:/tmp/audio_processing

  neo4j:
    image: neo4j:latest
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/password
    volumes:
      - neo4j_data:/data

  redis:
    image: redis:latest
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  # Background task worker for audio processing
  audio-worker:
    build: .
    environment:
      - GROQ_API_KEY=${GROQ_API_KEY}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - AUDIO_BUCKET_NAME=${AUDIO_BUCKET_NAME}
      - NEO4J_URI=bolt://neo4j:7687
      - REDIS_URL=redis://redis:6379
    depends_on:
      - neo4j
      - redis
    command: ["python", "-m", "app.workers.audio_processor"]

volumes:
  neo4j_data:
  redis_data:
```

---

## 📊 Monitoring & Analytics for Audio Processing

### **Audio Processing Analytics**
```python
# Analytics and monitoring for audio processing
from prometheus_client import Counter, Histogram, Gauge
import time

# Metrics
audio_processing_requests = Counter('audio_processing_requests_total', 'Total audio processing requests')
audio_processing_duration = Histogram('audio_processing_duration_seconds', 'Audio processing duration')
audio_upload_size = Histogram('audio_upload_size_bytes', 'Audio file upload sizes')
active_sessions = Gauge('active_audio_sessions', 'Currently active audio sessions')

class AudioAnalytics:
    def __init__(self):
        self.redis = get_redis_client()

    async def track_audio_request(self, user_id: str, audio_size: int, session_id: str):
        """Track audio processing request"""
        audio_processing_requests.inc()
        audio_upload_size.observe(audio_size)
        active_sessions.inc()

        # Store session start time
        await self.redis.setex(f"session_start:{session_id}", 3600, time.time())

    async def track_processing_completion(self, session_id: str, success: bool):
        """Track completion of audio processing"""
        active_sessions.dec()

        # Calculate processing time
        start_time = await self.redis.get(f"session_start:{session_id}")
        if start_time:
            duration = time.time() - float(start_time)
            audio_processing_duration.observe(duration)

            # Clean up
            await self.redis.delete(f"session_start:{session_id}")

    async def get_processing_stats(self) -> Dict:
        """Get current processing statistics"""
        return {
            "active_sessions": active_sessions._value._value,
            "total_requests": audio_processing_requests._value._value,
            "avg_processing_time": audio_processing_duration._sum._value / max(audio_processing_duration._count._value, 1)
        }
```

---

## 🎯 Updated Success Metrics for Alternative Architecture

### **Day 1 Success Criteria**
- [ ] Cloud storage (S3/GCS) integration working
- [ ] Audio upload/download pipeline operational
- [ ] Basic agent framework operational
- [ ] Database storing restaurant data
- [ ] Presigned URL generation for frontend uploads

### **Day 2 Success Criteria**
- [ ] Audio transcription via Groq Whisper working
- [ ] Food ordering agent providing recommendations
- [ ] Session management tracking audio processing
- [ ] Background task processing audio requests

### **Day 3 Success Criteria**
- [ ] Voice pattern analysis for cultural adaptation
- [ ] Health-aware filtering operational
- [ ] Multi-agent coordination working
- [ ] Audio response generation and cloud upload

### **Day 4 Success Criteria**
- [ ] Complete audio processing pipeline working
- [ ] Performance meets requirements (<10s total processing)
- [ ] Error handling and retry mechanisms robust
- [ ] Demo scenarios working end-to-end

---

## 🚀 Deployment Considerations

### **Cloud Storage Setup**
```bash
# AWS S3 bucket setup
aws s3 mb s3://aurasense-audio-files
aws s3api put-bucket-cors --bucket aurasense-audio-files --cors-configuration file://cors.json

# CORS configuration for direct frontend uploads
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "POST", "PUT"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }
  ]
}
```

### **Performance Expectations**
```text
Audio Processing Pipeline Timing:
- Audio Upload (Frontend → Cloud): 2-5 seconds
- Audio Download (Cloud → Backend): 1-2 seconds
- Transcription (Groq Whisper): 2-3 seconds
- Agent Processing: 2-4 seconds
- Response Generation: 1-2 seconds
- Response Upload: 1-2 seconds

Total Expected Time: 9-18 seconds (vs 3-5s for WebSocket)
Trade-off: Slightly slower but more scalable and reliable
```

This alternative architecture provides a more scalable, cloud-native approach to audio processing while maintaining all the cultural intelligence and agent capabilities of Aurasense. The bucket-based approach offers better reliability, easier debugging, and simpler deployment at the cost of slightly increased latency.
