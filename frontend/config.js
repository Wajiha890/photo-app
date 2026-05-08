/**
 * Azure / production: set your backend base URL (https only in production).
 * No trailing slash. Leave empty to use local defaults in Auth.js (Docker ports).
 *
 * Example after deploying App Service:
 *   window.__PX_API_BASE__ = "https://pixshare-api.azurewebsites.net";
 */
window.__PX_API_BASE__ = "https://pixshare-api.azurewebsites.net";
