class YouTubeFactChecker {
  constructor() {
    this.video = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.videoId = null;
    this.overlayContainer = null;
    this.claims = [];
    this.chunkDuration = 15000; // 15 seconds
    this.currentTime = 0;
    
    this.init();
  }

  init() {
    // Wait for video element to load
    this.waitForVideo();
    
    // Listen for messages from background script
    chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
      if (message.type === 'VERDICT_RECEIVED') {
        this.addClaimToOverlay(message.data);
      } else if (message.type === 'TOGGLE_ANALYSIS') {
        if (message.enabled) {
          this.startAnalysis();
        } else {
          this.stopAnalysis();
        }
      }
    });
  }

  waitForVideo() {
    const checkForVideo = () => {
      this.video = document.querySelector('video');
      if (this.video) {
        this.videoId = this.extractVideoId();
        this.setupVideoListeners();
        this.createOverlay();
        this.checkAutoAnalysis();
      } else {
        setTimeout(checkForVideo, 1000);
      }
    };
    checkForVideo();
  }

  extractVideoId() {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('v');
  }

  setupVideoListeners() {
    this.video.addEventListener('timeupdate', () => {
      this.currentTime = this.video.currentTime;
    });
    
    this.video.addEventListener('play', () => {
      this.checkAutoAnalysis();
    });
  }

  async checkAutoAnalysis() {
    const result = await chrome.storage.sync.get(['autoAnalysis']);
    if (result.autoAnalysis !== false) { // Default to true
      this.startAnalysis();
    }
  }

  createOverlay() {
    // Remove existing overlay if present
    const existing = document.getElementById('factcheck-overlay');
    if (existing) existing.remove();

    this.overlayContainer = document.createElement('div');
    this.overlayContainer.id = 'factcheck-overlay';
    this.overlayContainer.innerHTML = `
      <div id="factcheck-header">
        <h3>Fact Check</h3>
        <button id="factcheck-toggle">●</button>
      </div>
      <div id="factcheck-claims"></div>
    `;

    // Styling
    this.overlayContainer.style.cssText = `
      position: absolute;
      top: 10px;
      right: 10px;
      width: 300px;
      max-height: 400px;
      background: rgba(0, 0, 0, 0.9);
      color: white;
      border-radius: 8px;
      padding: 10px;
      font-family: Arial, sans-serif;
      font-size: 12px;
      z-index: 10000;
      overflow-y: auto;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    `;

    // Add to video container
    const videoContainer = document.querySelector('#movie_player') || 
                          document.querySelector('.html5-video-player');
    if (videoContainer) {
      videoContainer.appendChild(this.overlayContainer);
      
      // Add toggle functionality
      document.getElementById('factcheck-toggle').addEventListener('click', () => {
        const claims = document.getElementById('factcheck-claims');
        claims.style.display = claims.style.display === 'none' ? 'block' : 'none';
      });
    }
  }

  async startAnalysis() {
    if (this.isRecording || !this.video) return;

    try {
      // Capture audio stream from video
      const stream = this.video.captureStream();
      const audioStream = new MediaStream(stream.getAudioTracks());
      
      this.mediaRecorder = new MediaRecorder(audioStream, {
        mimeType: 'audio/webm;codecs=opus'
      });

      this.mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          this.audioChunks.push(event.data);
        }
      };

      this.mediaRecorder.onstop = () => {
        this.processAudioChunk();
      };

      this.isRecording = true;
      this.scheduleRecording();
      
      console.log('YouTube Fact Checker: Analysis started');
    } catch (error) {
      console.error('Error starting analysis:', error);
    }
  }

  scheduleRecording() {
    if (!this.isRecording) return;

    this.audioChunks = [];
    const startTime = this.currentTime;
    
    this.mediaRecorder.start();
    
    setTimeout(() => {
      if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
        this.mediaRecorder.stop();
        this.processAudioChunk(startTime);
      }
      
      // Schedule next chunk
      if (this.isRecording) {
        setTimeout(() => this.scheduleRecording(), 1000);
      }
    }, this.chunkDuration);
  }

  async processAudioChunk(startTime = this.currentTime) {
    if (this.audioChunks.length === 0) return;

    const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
    
    // Send to background script
    chrome.runtime.sendMessage({
      type: 'AUDIO_CHUNK',
      data: {
        audioBlob: await this.blobToBase64(audioBlob),
        videoId: this.videoId,
        timestamp: startTime,
        duration: this.chunkDuration / 1000
      }
    });
  }

  blobToBase64(blob) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result.split(',')[1]);
      reader.readAsDataURL(blob);
    });
  }

  stopAnalysis() {
    this.isRecording = false;
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.mediaRecorder = null;
    }
    console.log('YouTube Fact Checker: Analysis stopped');
  }

  addClaimToOverlay(claimData) {
    const claimsContainer = document.getElementById('factcheck-claims');
    if (!claimsContainer) return;

    const claimElement = document.createElement('div');
    claimElement.className = 'factcheck-claim';
    
    const verdictColor = {
      'Real': '#4CAF50',
      'Fake': '#F44336',
      'Unclear': '#FF9800'
    }[claimData.verdict] || '#9E9E9E';

    claimElement.innerHTML = `
      <div style="border-left: 3px solid ${verdictColor}; padding-left: 8px; margin: 8px 0;">
        <div style="font-weight: bold; color: ${verdictColor};">
          ${claimData.verdict} (${claimData.confidence}%)
        </div>
        <div style="margin: 4px 0; font-size: 11px; color: #ccc;">
          ${this.formatTime(claimData.timestamp)}
        </div>
        <div style="margin: 4px 0;">
          "${claimData.claim}"
        </div>
        ${claimData.sources.map(source => 
          `<a href="${source}" target="_blank" style="color: #4FC3F7; font-size: 10px; display: block;">
            ${new URL(source).hostname}
          </a>`
        ).join('')}
      </div>
    `;

    claimsContainer.appendChild(claimElement);
    
    // Limit to 10 claims
    while (claimsContainer.children.length > 10) {
      claimsContainer.removeChild(claimsContainer.firstChild);
    }
  }

  formatTime(seconds) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => new YouTubeFactChecker());
} else {
  new YouTubeFactChecker();
}