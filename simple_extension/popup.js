// Simple test popup for native messaging

// Get DOM elements
const testButton = document.getElementById('testButton');
const pingButton = document.getElementById('pingButton');
const clearButton = document.getElementById('clearButton');
const responseDiv = document.getElementById('response');

// Log to the response div
function log(message) {
  const timestamp = new Date().toLocaleTimeString();
  responseDiv.textContent += `[${timestamp}] ${message}\n`;
  responseDiv.scrollTop = responseDiv.scrollHeight;
}

// Clear log
function clearLog() {
  responseDiv.textContent = '';
}

// Test extension info
function testExtension() {
  log(`Extension ID: ${chrome.runtime.id}`);
  log(`Extension version: ${chrome.runtime.getManifest().version}`);
  log(`Has nativeMessaging permission: ${chrome.runtime.getManifest().permissions.includes('nativeMessaging')}`);
}

// Send a message to the native host
function pingHost() {
  log('Sending ping to native host...');
  
  try {
    chrome.runtime.sendNativeMessage(
      'com.copyboard.extension',
      { action: 'ping', message: 'Hello from extension!' },
      (response) => {
        if (chrome.runtime.lastError) {
          log(`Error: ${chrome.runtime.lastError.message}`);
        } else {
          log(`Response received: ${JSON.stringify(response)}`);
        }
      }
    );
  } catch (error) {
    log(`Exception: ${error.message}`);
  }
}

// Add event listeners
testButton.addEventListener('click', testExtension);
pingButton.addEventListener('click', pingHost);
clearButton.addEventListener('click', clearLog);

// Log startup
log('Popup opened');
testExtension();
