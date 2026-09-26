export function updateAuthUI(isLoggedIn, userProfile = null) {
    const signinBtn = document.querySelector('.sign-in-btn');
    const logoutBtn = document.querySelector('.logout-btn');
    const userDisplay = document.querySelector('.user-display');

    if (isLoggedIn) {
        signinBtn.style.display = 'none';
        logoutBtn.style.display = 'inline-block';

        if (userProfile && userDisplay) {
            userDisplay.textContent = `Hello, ${userProfile.display_name || userProfile.email}`;
            userDisplay.style.display = 'inline-block';
        }
    } else {
        signinBtn.style.display = 'inline-block';
        logoutBtn.style.display = 'none';

        if (userDisplay) {
            userDisplay.textContent = '';
            userDisplay.style.display = 'none';
        }
    }
}


// ======= Fetch Profile and Update UI =======
export async function fetchProfile(token = localStorage.getItem("token")) {
    try {
        const res = await fetch('/auth/me', {
            headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) throw new Error("Invalid token");
        const profile = await res.json();
        updateAuthUI(true, profile);
        console.log("User Profile:", profile);
    } catch (err) {
        console.warn("Failed to fetch profile");
        localStorage.removeItem("token");
        updateAuthUI(false);
    }
}