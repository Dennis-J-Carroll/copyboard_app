// Copyboard Browser Extension - Content Script

// Debug logging function
function log(message) {
  console.log('[Copyboard Content Script]', message);
}

// Log script initialization
log('Content script loaded');

// Listen for messages from the background script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  log('Received message: ' + JSON.stringify(message));
  
  if (message.action === "paste-content") {
    log('Pasting content: ' + truncateText(message.content, 30));
    // Paste the content at the current selection
    pasteContent(message.content);
    sendResponse({ success: true });
  } else if (message.action === "prepare-paste") {
    log('Preparing for paste');
    // Store the current selection for later use
    storeCurrentSelection();
    sendResponse({ success: true });
  } else if (message.action === "show-radial") {
    log('Showing radial menu');
    // Show the radial menu
    showRadialMenu();
    sendResponse({ success: true });
  }
  
  return true; // Keep channel open for async response
});

// Injection check - add this to the page to verify content script is running
const injectionMarker = document.createElement('div');
injectionMarker.id = 'copyboard-injection-marker';
injectionMarker.style.display = 'none';
document.body.appendChild(injectionMarker);
log('Injection marker added to page');

// Store the current selection for later use
let storedSelection = null;
function storeCurrentSelection() {
  try {
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
      storedSelection = selection.getRangeAt(0);
      log('Selection stored successfully');
      return true;
    }
  } catch (e) {
    log('Error storing selection: ' + e.message);
  }
  return false;
}

// Paste content at the current selection
function pasteContent(content) {
  log('pasteContent called with: ' + truncateText(content, 30));
  
  try {
    // Restore selection if needed
    if (storedSelection) {
      log('Restoring stored selection');
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(storedSelection);
      storedSelection = null;
    }
    
    // Check if we're in an editable element
    const activeElement = document.activeElement;
    log('Active element: ' + (activeElement.tagName || 'unknown') + 
        ', contentEditable: ' + activeElement.isContentEditable);
    
    if (activeElement.isContentEditable || 
        activeElement.tagName === 'INPUT' || 
        activeElement.tagName === 'TEXTAREA') {
      
      // Different approach based on element type
      if (activeElement.isContentEditable) {
        log('Pasting into contentEditable element');
        // For contentEditable elements
        document.execCommand('insertText', false, content);
      } else {
        log('Pasting into input/textarea element');
        // For input/textarea elements
        const start = activeElement.selectionStart;
        const end = activeElement.selectionEnd;
        const beforeText = activeElement.value.substring(0, start);
        const afterText = activeElement.value.substring(end);
        
        // Set new value and update cursor position
        activeElement.value = beforeText + content + afterText;
        activeElement.selectionStart = activeElement.selectionEnd = start + content.length;
        
        // Trigger input event for JS frameworks
        const event = new Event('input', { bubbles: true });
        activeElement.dispatchEvent(event);
      }
      log('Paste completed successfully');
      return true;
    } else {
      log('No editable element found for pasting');
    }
  } catch (e) {
    log('Error during paste: ' + e.message);
  }
  return false;
}

// Handle paste with fallback mechanisms
function handlePaste(content) {
  // Try direct paste first
  if (pasteContent(content)) return;
  
  // Fallback: create a temporary textarea
  log('Using fallback paste mechanism');
  const textarea = document.createElement('textarea');
  textarea.value = content;
  textarea.style.position = 'fixed';
  textarea.style.opacity = 0;
  document.body.appendChild(textarea);
  textarea.select();
  
  try {
    // Use document.execCommand as fallback
    const success = document.execCommand('paste');
    log('Fallback paste ' + (success ? 'succeeded' : 'failed'));
  } catch (e) {
    log('Fallback paste error: ' + e.message);
  }
  
  document.body.removeChild(textarea);
}

// Show radial menu at cursor position
function showRadialMenu() {
  log('Creating radial menu overlay');
  
  try {
    // Create an overlay div for the radial menu
    const overlay = document.createElement('div');
    overlay.id = 'copyboard-radial-overlay';
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100%';
    overlay.style.height = '100%';
    overlay.style.zIndex = '9999999';
    overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.3)';
    overlay.style.display = 'flex';
    overlay.style.justifyContent = 'center';
    overlay.style.alignItems = 'center';
    
    // Close on escape key
    document.addEventListener('keydown', function escHandler(e) {
      if (e.key === 'Escape') {
        log('Closing radial menu on Escape key');
        document.body.removeChild(overlay);
        document.removeEventListener('keydown', escHandler);
      }
    });
    
    // Close on overlay click
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        log('Closing radial menu on overlay click');
        document.body.removeChild(overlay);
      }
    });
    
    // Add to document
    document.body.appendChild(overlay);
    
    // Create loading indicator
    const loader = document.createElement('div');
    loader.textContent = 'Loading clipboard items...';
    loader.style.color = 'white';
    loader.style.padding = '20px';
    loader.style.borderRadius = '5px';
    loader.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
    overlay.appendChild(loader);
    
    // Send message to background script to get clipboard items
    log('Requesting clipboard items from background');
    chrome.runtime.sendMessage({
      action: "get-clipboard-items"
    }, (response) => {
      log('Received clipboard items response: ' + JSON.stringify(response));
      // Remove loader
      overlay.removeChild(loader);
      
      if (response && response.items && response.items.length > 0) {
        // Create the radial menu with items
        createRadialMenu(overlay, response.items);
      } else {
        // Show no items message
        const noItems = document.createElement('div');
        noItems.textContent = 'No clipboard items available';
        noItems.style.color = 'white';
        noItems.style.padding = '20px';
        noItems.style.borderRadius = '5px';
        noItems.style.backgroundColor = 'rgba(0, 0, 0, 0.7)';
        overlay.appendChild(noItems);
        
        // Auto close after 2 seconds
        setTimeout(() => {
          if (document.body.contains(overlay)) {
            document.body.removeChild(overlay);
          }
        }, 2000);
      }
    });
  } catch (e) {
    log('Error showing radial menu: ' + e.message);
  }
}

// Create radial menu with items
function createRadialMenu(overlay, items) {
  log('Creating radial menu with ' + items.length + ' items');
  
  try {
    // Create menu container
    const menu = document.createElement('div');
    menu.id = 'copyboard-radial-menu';
    menu.style.background = 'white';
    menu.style.borderRadius = '10px';
    menu.style.boxShadow = '0 0 20px rgba(0, 0, 0, 0.5)';
    menu.style.maxWidth = '80%';
    menu.style.maxHeight = '80%';
    menu.style.overflow = 'auto';
    menu.style.zIndex = '10000000';
    menu.style.padding = '10px';
    
    // Add title
    const title = document.createElement('div');
    title.textContent = 'Select item to paste:';
    title.style.padding = '10px';
    title.style.borderBottom = '1px solid #ccc';
    title.style.marginBottom = '10px';
    title.style.fontWeight = 'bold';
    menu.appendChild(title);
    
    // Add items container
    const itemsContainer = document.createElement('div');
    itemsContainer.style.display = 'flex';
    itemsContainer.style.flexDirection = 'column';
    itemsContainer.style.gap = '5px';
    
    // Add items
    items.forEach((item, index) => {
      const itemElem = document.createElement('div');
      itemElem.textContent = `${index}: ${truncateText(item, 50)}`;
      itemElem.style.padding = '8px 15px';
      itemElem.style.cursor = 'pointer';
      itemElem.style.borderRadius = '5px';
      itemElem.style.transition = 'background-color 0.2s';
      
      // Hover effect
      itemElem.addEventListener('mouseover', () => {
        itemElem.style.backgroundColor = '#f0f0f0';
      });
      itemElem.addEventListener('mouseout', () => {
        itemElem.style.backgroundColor = 'transparent';
      });
      
      // Add click handler
      itemElem.addEventListener('click', () => {
        log('Item selected: ' + index);
        // Paste this item
        pasteContent(item);
        
        // Remove menu and overlay
        if (document.body.contains(overlay)) {
          document.body.removeChild(overlay);
        }
      });
      
      itemsContainer.appendChild(itemElem);
    });
    
    menu.appendChild(itemsContainer);
    overlay.appendChild(menu);
    
    // Add keyboard handling
    document.addEventListener('keydown', function keyHandler(e) {
      // Handle number keys 0-9
      const num = parseInt(e.key);
      if (!isNaN(num) && num >= 0 && num < items.length) {
        log('Item selected via keyboard: ' + num);
        pasteContent(items[num]);
        document.body.removeChild(overlay);
        document.removeEventListener('keydown', keyHandler);
      }
    });
  } catch (e) {
    log('Error creating radial menu: ' + e.message);
  }
}

// Helper function to truncate text
function truncateText(text, maxLength) {
  if (!text) return '';
  if (text.length <= maxLength) {
    return text;
  }
  return text.substr(0, maxLength) + "...";
}

// Log that content script is fully initialized
log('Content script fully initialized');

