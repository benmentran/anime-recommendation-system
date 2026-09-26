import { fetchProfile, updateAuthUI } from './profile.js';


export function initAuthHandlers() {
    // ======= DOM Elements =======
    const signinBtns = document.querySelectorAll('.sign-in-btn');
    const signupBtns = document.querySelectorAll('.sign-up-btn');

    const signinModal = document.getElementById('signinModal');
    const signupModal = document.getElementById('signupModal');

    const closeSignin = document.getElementById('closeSignin');
    const closeSignup = document.getElementById('closeSignup');

    const signinForm = document.getElementById('signinForm');
    const signupForm = document.getElementById('signupForm');

    // ======= Toggle Modal =======
    signinBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            signinModal.style.display = 'flex';
            signupModal.style.display = 'none';
        });
    });

    signupBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            signupModal.style.display = 'flex';
            signinModal.style.display = 'none';
        });
    });

    closeSignin?.addEventListener('click', () => signinModal.style.display = 'none');
    closeSignup?.addEventListener('click', () => signupModal.style.display = 'none');

    window.addEventListener('click', (e) => {
        if (e.target === signinModal) signinModal.style.display = 'none';
        if (e.target === signupModal) signupModal.style.display = 'none';
    });

    // ======= Sign In Submit =======
    signinForm?.addEventListener('submit', async (e) => {
        e.preventDefault();

        const email = document.getElementById("signin-email").value.trim();
        const password = document.getElementById("signin-password").value.trim();

        if (!validateEmail(email)) return alert("Invalid email format");
        if (password.length < 6) return alert("Password must be at least 6 characters");

        try {
            const res = await fetch('/auth/signin', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ email, password }),
            });

            const data = await res.json();

            if (res.ok && data.access_token) {
                localStorage.setItem("token", data.access_token);
                console.log("Token saved to localStorage:", data.access_token);
                document.cookie = `token=${data.access_token}; path=/;`;

                alert("Signed in successfully!");

                signinModal.style.display = 'none';
                window.location.href = "/browse";
                fetchProfile();
            } else {
                alert(data.detail || "Login failed");
            }
        } catch (err) {
            console.error(err);
            alert("Server error");
        }
    });

    // ======= Sign Up Submit =======
    signupForm?.addEventListener('submit', async (e) => {
        e.preventDefault();

        const name = document.getElementById("signup-name").value.trim();
        const email = document.getElementById("signup-email").value.trim();
        const password = document.getElementById("signup-password").value.trim();

        if (!name) return alert("Name required");
        if (!validateEmail(email)) return alert("Invalid email");
        if (password.length < 6) return alert("Password too short");

        try {
            const res = await fetch('/auth/signup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ display_name: name, email, password }),
            });

            const data = await res.json();
            if (!res.ok) return alert(data.detail || "Signup failed");

            alert("Registered! Please sign in.");
            signupModal.style.display = 'none';
            signinModal.style.display = 'flex';
        } catch (err) {
            console.error(err);
            alert("Server error");
        }
    });

    // ======= Auto Fetch Profile (if token exists) =======
    const token = localStorage.getItem('token');
    if (token) fetchProfile(token);
}

// ======= Google Login Handler =======
window.handleGoogleLogin = async function (response) {
    try {
        const res = await fetch('/api/google-login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ credential: response.credential }),
        });

        const data = await res.json();
        if (data.success) {
            alert("Google login successful!");
            localStorage.setItem("token", data.token);
            window.location.href = "/browse";
            fetchProfile();
        } else {
            alert(data.message || "Google login failed");
        }
    } catch (err) {
        console.error(err);
        alert("Google login server error");
    }
};

// ======= Validate Email =======
function validateEmail(email) {
    return /\S+@\S+\.\S+/.test(email);
}

// ======= Logout =======
export function initLogoutHandler() {
    const logoutBtn = document.querySelector('.logout-btn');
    logoutBtn?.addEventListener('click', () => {
        localStorage.removeItem('token');
        window.location.href = "/";
        alert("Logged out!");
        updateAuthUI(false);
    });
}
