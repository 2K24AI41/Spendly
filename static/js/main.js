// main.js — students will add JavaScript here as features are built

// Registration: warn before submit when the two passwords differ.
// The server re-checks this; this only gives instant feedback.
document.addEventListener("DOMContentLoaded", function () {
    var password = document.getElementById("password");
    var confirmPassword = document.getElementById("confirm_password");
    if (!password || !confirmPassword) {
        return;
    }

    function checkMatch() {
        if (confirmPassword.value && confirmPassword.value !== password.value) {
            confirmPassword.setCustomValidity("Passwords do not match.");
        } else {
            confirmPassword.setCustomValidity("");
        }
    }

    password.addEventListener("input", checkMatch);
    confirmPassword.addEventListener("input", checkMatch);
});
