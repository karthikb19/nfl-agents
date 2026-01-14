/**
 * NFL Agent Chat - Client-side JavaScript
 * Handles SSE streaming, dynamic UI updates, and chat interactions
 */

class NFLAgentChat {
  constructor() {
    this.chatContainer = document.getElementById('chat-container');
    this.inputForm = document.getElementById('input-form');
    this.inputField = document.getElementById('input-field');
    this.sendButton = document.getElementById('send-button');
    this.emptyState = document.getElementById('empty-state');
    
    this.isProcessing = false;
    this.thinkingElement = null;
    
    this.init();
  }
  
  init() {
    // Form submission
    this.inputForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this.sendMessage();
    });
    
    // Auto-resize textarea
    this.inputField.addEventListener('input', () => {
      this.autoResize();
    });
    
    // Enter to send (Shift+Enter for newline)
    this.inputField.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        this.sendMessage();
      }
    });
    
    // Focus input on page load
    this.inputField.focus();
  }
  
  autoResize() {
    this.inputField.style.height = 'auto';
    this.inputField.style.height = Math.min(this.inputField.scrollHeight, 120) + 'px';
  }
  
  async sendMessage() {
    const message = this.inputField.value.trim();
    if (!message || this.isProcessing) return;
    
    this.isProcessing = true;
    this.sendButton.disabled = true;
    
    // Hide empty state
    if (this.emptyState) {
      this.emptyState.classList.add('hidden');
    }
    
    // Add user message to UI
    this.addMessage(message, 'user');
    
    // Clear input
    this.inputField.value = '';
    this.autoResize();
    
    // Show thinking indicator
    this.showThinking();
    
    try {
      await this.streamResponse(message);
    } catch (error) {
      console.error('Error:', error);
      this.addMessage('Sorry, something went wrong. Please try again.', 'assistant');
    } finally {
      this.hideThinking();
      this.isProcessing = false;
      this.sendButton.disabled = false;
      this.inputField.focus();
    }
  }
  
  async streamResponse(message) {
    const response = await fetch('/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error: ${response.status}`);
    }
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() || '';
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = JSON.parse(line.slice(6));
          this.handleStreamEvent(data);
        }
      }
    }
  }
  
  handleStreamEvent(data) {
    switch (data.type) {
      case 'thinking':
        this.updateThinkingText(data.content);
        break;
      
      case 'step':
        this.addStep(data.action, data.success);
        break;
      
      case 'answer':
        this.hideThinking();
        this.addMessage(data.content, 'assistant');
        break;
      
      case 'error':
        this.hideThinking();
        this.addMessage(data.content, 'assistant');
        break;
      
      case 'done':
        // Response complete
        break;
    }
  }
  
  addMessage(content, role) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message--${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message__content';
    contentDiv.textContent = content;
    
    messageDiv.appendChild(contentDiv);
    this.chatContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    this.scrollToBottom();
  }
  
  showThinking() {
    this.thinkingElement = document.createElement('div');
    this.thinkingElement.className = 'thinking';
    this.thinkingElement.innerHTML = `
      <div class="thinking__dots">
        <span class="thinking__dot"></span>
        <span class="thinking__dot"></span>
        <span class="thinking__dot"></span>
      </div>
      <span class="thinking__text">Thinking...</span>
      <div class="thinking__steps"></div>
    `;
    this.chatContainer.appendChild(this.thinkingElement);
    this.scrollToBottom();
  }
  
  hideThinking() {
    if (this.thinkingElement) {
      this.thinkingElement.remove();
      this.thinkingElement = null;
    }
  }
  
  updateThinkingText(text) {
    if (this.thinkingElement) {
      const textEl = this.thinkingElement.querySelector('.thinking__text');
      if (textEl) {
        textEl.textContent = text;
      }
    }
  }
  
  addStep(action, success) {
    if (!this.thinkingElement) return;
    
    const stepsContainer = this.thinkingElement.querySelector('.thinking__steps');
    if (!stepsContainer) return;
    
    const pill = document.createElement('span');
    pill.className = `step-pill ${success ? 'step-pill--success' : 'step-pill--pending'}`;
    pill.textContent = action;
    stepsContainer.appendChild(pill);
    
    // Update thinking text based on action
    const actionTexts = {
      'sql': 'Querying database...',
      'web': 'Searching the web...',
    };
    this.updateThinkingText(actionTexts[action] || 'Processing...');
  }
  
  scrollToBottom() {
    this.chatContainer.scrollTop = this.chatContainer.scrollHeight;
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  new NFLAgentChat();
});
