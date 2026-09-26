export function initThemeSwitcher() {
    const themeBtn = document.getElementById('themeSwitcher');
    if (!themeBtn) return;

    let mode = localStorage.getItem('theme') || 'dark';
    setTheme(mode);

    themeBtn.addEventListener('click', () => {
        const newMode = document.body.classList.contains('dark-theme') ? 'light' : 'dark';
        setTheme(newMode);
    });

    function setTheme(mode) {
        document.body.classList.remove('light-theme', 'dark-theme');
        document.body.classList.add(mode + '-theme');

        themeBtn.innerHTML = mode === 'light'
            ? '<i class="fas fa-sun" aria-hidden="true"></i> Light Mode'
            : '<i class="fas fa-moon" aria-hidden="true"></i> Dark Mode';

        localStorage.setItem('theme', mode);
    }
}


export function initSettingsMenu() {
    console.log("⚙️ initSettingsMenu called");
    document.querySelectorAll('.settings-toggle').forEach(toggleBtn => {
        console.log("– found toggleBtn", toggleBtn);
        const menu = toggleBtn.nextElementSibling;
        toggleBtn.addEventListener('click', e => {
            e.stopPropagation();
            menu.classList.toggle('show');
        });
    });

    document.addEventListener('click', () => {
        document.querySelectorAll('.settings-menu.show').forEach(menu => {
            menu.classList.remove('show');
        });
    });
}
