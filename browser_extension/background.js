// Copyboard Browser Extension - Background Script

// Print extension ID and details immediately
console.log('Extension ID:', chrome.runtime.id);
console.log('Manifest:', JSON.stringify(chrome.runtime.getManifest()));

// DIAGNOSTIC: Alert the extension ID for easier debugging
const extensionId = chrome.runtime.id;
alert(`Copyboard Extension ID: ${extensionId}\n\nMake sure this ID matches the one in your native messaging host manifest!`);

// Save ID to storage for reference
chrome.storage.local.set({extensionId: extensionId});

// Debug logging function
function logDebug(message) {
  console.log('[Copyboard Debug]', message);
}

// Initialize extension
chrome.runtime.onInstalled.addListener(() => {
  logDebug('Extension installed/updated');
  
  // Clear any existing context menus
  chrome.contextMenus.removeAll();
  
  // Create main menu
  chrome.contextMenus.create({
    id: "copyboard-main",
    title: "Copyboard",
    contexts: ["all"]
  });

  // Copy to board
  chrome.contextMenus.create({
    id: "copyboard-add",
    parentId: "copyboard-main",
    title: "Copy to Clipboard Board",
    contexts: ["selection"]
  });

  // Paste from board
  chrome.contextMenus.create({
    id: "copyboard-paste",
    parentId: "copyboard-main",
    title: "Paste from Clipboard Board",
    contexts: ["editable"]
  });

  // Paste radial
  chrome.contextMenus.create({
    id: "copyboard-radial",
    parentId: "copyboard-main",
    title: "Paste with Radial Menu",
    contexts: ["editable"]
  });
  
  // Store empty clipboard board in storage
  chrome.storage.local.set({ clipboardItems: [] });
});

// Listen for messages from content script
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  logDebug('Received message: ' + JSON.stringify(message));
  
  if (message.action === "get-clipboard-items") {
    // Fetch items from native messaging host
    sendNativeMessage({
      action: "list"
    }, (response) => {
      if (response && response.items) {
        logDebug('Retrieved clipboard items: ' + response.items.length);
        sendResponse({ items: response.items });
      } else {
        logDebug('No clipboard items or error in response');
        sendResponse({ items: [] });
      }
    });
    return true; // Indicate we'll respond asynchronously
  }
  
  if (message.action === "add-to-board") {
    sendNativeMessage({
      action: "add",
      content: message.content
    }, (response) => {
      sendResponse({ success: response && response.success });
    });
    return true;
  }
  
  if (message.action === "clear-board") {
    sendNativeMessage({
      action: "clear"
    }, (response) => {
      sendResponse({ success: response && response.success });
    });
    return true;
  }
});

// Handle context menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  logDebug('Context menu clicked: ' + info.menuItemId);
  
  switch (info.menuItemId) {
    case "copyboard-add":
      // Get the selected text
      if (info.selectionText) {
        logDebug('Adding text to clipboard board: ' + truncateText(info.selectionText, 30));
        
        // Send message to native host
        sendNativeMessage({
          action: "add",
          content: info.selectionText
        }, (response) => {
          if (response && response.success) {
            // Show notification
            chrome.action.setBadgeText({ text: "✓" });
            setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 1500);
          }
        });
      }
      break;
    
    case "copyboard-paste":
      logDebug('Preparing paste menu');
      
      // Get clipboard items from native host
      sendNativeMessage({
        action: "list"
      }, (response) => {
        if (response && response.items && response.items.length > 0) {
          logDebug('Creating paste submenu with ' + response.items.length + ' items');
          
          // Remove any existing items
          chrome.contextMenus.removeAll(() => {
            // Recreate main menu
            chrome.contextMenus.create({
              id: "copyboard-paste-submenu",
              title: "Paste from Copyboard",
              contexts: ["editable"]
            });
            
            // Create items
            response.items.forEach((item, index) => {
              chrome.contextMenus.create({
                id: `copyboard-item-${index}`,
                parentId: "copyboard-paste-submenu",
                title: `${index}: ${truncateText(item, 30)}`,
                contexts: ["editable"]
              });
            });
          });
        } else {
          logDebug('No clipboard items found');
        }
      });
      break;
    
    case "copyboard-radial":
      logDebug('Showing radial menu');
      
      // Send message to content script
      chrome.tabs.sendMessage(tab.id, {
        action: "show-radial"
      });
      break;
      
    default:
      // Check if it's a clipboard item
      if (info.menuItemId.startsWith("copyboard-item-")) {
        const index = parseInt(info.menuItemId.split("-")[2]);
        logDebug('Pasting clipboard item at index: ' + index);
        
        // Get the content from native host
        sendNativeMessage({
          action: "paste",
          index: index
        }, (response) => {
          if (response && response.content) {
            logDebug('Retrieved content from native host, sending to content script');
            
            // Send the content to the content script for pasting
            chrome.tabs.sendMessage(tab.id, {
              action: "paste-content",
              content: response.content
            });
          } else {
            logDebug('Failed to retrieve content from native host');
          }
        });
      }
      break;
  }
});

// Native messaging with host
function sendNativeMessage(message, callback) {
  logDebug('Sending native message: ' + JSON.stringify(message));
  
  // Show loading indicator
  chrome.action.setBadgeText({ text: "..." });
  chrome.action.setBadgeBackgroundColor({ color: "#4285F4" });
  
  try {
    chrome.runtime.sendNativeMessage(
      "com.copyboard.extension",
      message,
      (response) => {
        // Clear loading indicator
        chrome.action.setBadgeText({ text: "" });
        
        if (chrome.runtime.lastError) {
          const errorMessage = chrome.runtime.lastError.message;
          logDebug('Error sending native message: ' + errorMessage);
          
          // Show error indicator
          chrome.action.setBadgeText({ text: "!" });
          chrome.action.setBadgeBackgroundColor({ color: "#F44336" });
          setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 3000);
          
          // Show notification with error details
          chrome.notifications.create({
            type: 'basic',
            iconUrl: 'icons/icon128.png',
            title: 'Copyboard Error',
            message: 'Native messaging error: ' + errorMessage.substring(0, 100)
          });
          
          callback && callback(null);
        } else {
          logDebug('Native message response: ' + JSON.stringify(response));
          
          // Show success indicator briefly
          if (response && response.success) {
            chrome.action.setBadgeText({ text: "✓" });
            chrome.action.setBadgeBackgroundColor({ color: "#4CAF50" });
            setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 1500);
          } else if (response) {
            // Show error from response
            chrome.action.setBadgeText({ text: "!" });
            chrome.action.setBadgeBackgroundColor({ color: "#FF9800" });
            setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 1500);
            
            logDebug('Response indicates error: ' + (response.error || 'Unknown error'));
          }
          
          callback && callback(response);
        }
      }
    );
  } catch (e) {
    logDebug('Exception sending native message: ' + e.message);
    
    // Clear loading and show error
    chrome.action.setBadgeText({ text: "!" });
    chrome.action.setBadgeBackgroundColor({ color: "#F44336" });
    setTimeout(() => { chrome.action.setBadgeText({ text: "" }); }, 3000);
    
    callback && callback(null);
  }
}

// Helper function to truncate text
function truncateText(text, maxLength) {
  if (!text) return "";
  if (text.length <= maxLength) {
    return text;
  }
  return text.substr(0, maxLength) + "...";
}
