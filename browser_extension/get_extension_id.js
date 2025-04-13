// This script logs the extension ID
console.log("Extension ID:", chrome.runtime.id);

// We also log the manifest to see the full details
console.log("Manifest:", chrome.runtime.getManifest());

// Add this at the beginning of the background.js file
// Or load this directly in the extension console
