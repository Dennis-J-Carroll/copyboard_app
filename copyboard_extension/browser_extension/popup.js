// Copyboard Browser Extension - Popup Script

document.addEventListener('DOMContentLoaded', () => {
  // Get elements
  const itemsContainer = document.getElementById('items-container');
  const addButton = document.getElementById('add-btn');
  const clearButton = document.getElementById('clear-btn');
  
  // Load clipboard items
  loadClipboardItems();
  
  // Add event listeners
  addButton.addEventListener('click', addCurrentToBoard);
  clearButton.addEventListener('click', clearClipboardBoard);
});

// Load clipboard items from the native application
function loadClipboardItems() {
  const itemsContainer = document.getElementById('items-container');
  
  // Clear the container
  itemsContainer.innerHTML = '<div class="empty">Loading clipboard items...</div>';
  
  // Send message to background script
  chrome.runtime.sendMessage({
    action: "get-clipboard-items"
  }, (response) => {
    if (response && response.items && response.items.length > 0) {
      // Clear the container again
      itemsContainer.innerHTML = '';
      
      // Add each item
      response.items.forEach((item, index) => {
        addItemToList(item, index);
      });
    } else {
      // Show empty message
      itemsContainer.innerHTML = '<div class="empty">No items in clipboard board</div>';
    }
  });
}

// Add an item to the list
function addItemToList(text, index) {
  const itemsContainer = document.getElementById('items-container');
  
  // Create item element
  const item = document.createElement('div');
  item.className = 'item';
  item.dataset.index = index;
  
  // Create item number
  const itemNumber = document.createElement('div');
  itemNumber.className = 'item-number';
  itemNumber.textContent = index;
  item.appendChild(itemNumber);
  
  // Create item text
  const itemText = document.createElement('div');
  itemText.className = 'item-text';
  itemText.textContent = text.replace(/\n/g, ' ');
  item.appendChild(itemText);
  
  // Add click handler
  item.addEventListener('click', () => {
    // Copy this item to clipboard
    copyToClipboard(text);
    
    // Close popup
    window.close();
  });
  
  // Add to container
  itemsContainer.appendChild(item);
}

// Add current clipboard content to board
function addCurrentToBoard() {
  // Get text from clipboard
  navigator.clipboard.readText().then(text => {
    if (text) {
      // Send message to native application
      chrome.runtime.sendMessage({
        action: "add-to-board",
        content: text
      }, () => {
        // Reload items
        loadClipboardItems();
      });
    }
  }).catch(err => {
    console.error('Failed to read clipboard:', err);
  });
}

// Clear the clipboard board
function clearClipboardBoard() {
  // Send message to native application
  chrome.runtime.sendMessage({
    action: "clear-board"
  }, () => {
    // Reload items
    loadClipboardItems();
  });
}

// Copy text to clipboard
function copyToClipboard(text) {
  navigator.clipboard.writeText(text).catch(err => {
    console.error('Failed to copy text:', err);
  });
}
