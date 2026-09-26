import { initThemeSwitcher, initSettingsMenu } from './theme.js';
import { initAuthHandlers, initLogoutHandler } from './auth.js';
import { fetchProfile } from './profile.js';

document.addEventListener("DOMContentLoaded", () => {
    initThemeSwitcher()
    initSettingsMenu()
    initAuthHandlers();
    initLogoutHandler();
    const token = localStorage.getItem('token');
    if (token) fetchProfile(token);
})
