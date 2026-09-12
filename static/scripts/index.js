let roomCodeEl = document.getElementById("room-code-input");
let helpEl = document.getElementById("help-popup");
let menuEl = document.getElementById("index-menu");
let deckSelectPopUpEl = document.getElementById("deck-select-popup");
let deckFilterEl = document.getElementById("deck-filter");
let playlistSelectDivEl = document.getElementById("playlist-select-div");
let toggleDropdownEl = document.querySelector(".toggle-dropdown");
let toggleTextEl = document.getElementById("toggle-text");
let optionsDropdownEl = document.querySelector(".options-dropdown");

let deckName = null;

document.addEventListener("click", (event) => {
    if (!playlistSelectDivEl.contains(event.target)) {
        optionsDropdownEl.style.display = "none";
        toggleDropdownEl.classList.remove('open');
    }
});

roomCodeEl.addEventListener("input", (event) => {
    event.target.value = event.target.value.toUpperCase();
});

toggleDropdownEl.addEventListener("click", () => {
    if (optionsDropdownEl.style.display != "block") {
        optionsDropdownEl.style.display = "block";
        toggleDropdownEl.classList.toggle('open');
        deckFilterEl.focus();
    } else {
        optionsDropdownEl.style.display = "none";
        toggleDropdownEl.classList.remove('open');
    }
})

deckFilterEl.addEventListener("input", (e) => {
    let toMatch = deckFilterEl.value;
    for (let option of optionsDropdownEl.getElementsByClassName("deck-item")) {
        if (option.getAttribute("data-val").startsWith(toMatch)) {
            option.style.display = "block";
        } else {
            option.style.display = "none";
        }
    }
})

function sendCreateRequest() {
    if (deckName == null) {
        deckSelectPopUpEl.innerHTML = "Please select a valid deck.";
        deckSelectPopUpEl.style.display = "block";
        setTimeout(() => {
            deckSelectPopUpEl.style.display = "none";
        }, 1500);
        return;
    }
    fetch("/create-room-rq", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deck: deckName })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json()
    })
    .then(data => {
        const regexTest = /^\/multiplayer\?room=[A-Z]{4}$/
        if (!regexTest.test(data.url)) {
            throw new Error('Returned URL not ok');
        }
        window.location.href = data.url;
    })
    .catch((error) => console.error("Error:", error));
}

function sendJoinRequest() {
    let code = roomCodeEl.value
    const regexTest = /^[A-Z]+$/;
    if (code.length != 4 || !regexTest.test(code)) {
        alert("Please enter a valid code.");
        return;
    }

    fetch("/join-room-rq", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room_code: code })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json()
    })
    .then(data => {
        if (data.url == undefined || data.url === "") {
            alert("The room you are trying to enter is full or invalid");
        return;
        }
        const regexTest = /^\/multiplayer\?room=[A-Z]{4}$/
        if (!regexTest.test(data.url)) {
            throw new Error('Returned URL not ok');
        }
        window.location.href = data.url;
    })
    .catch((error) => console.error("Error:", error));
}

function sendToDeckViewer() {
    fetch("/deckviewer", {
        method: "GET"
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        if (response.url == undefined || response.url == "") {
            throw new Error('Returned URL not ok')
        }
        window.location.href = response.url;
    })
    .catch((error) => console.error("Error:", error));
}

function addTabs() {
    let buttons = document.getElementsByClassName("custom-button");
    for (let el of buttons) {
        el.tabIndex = 0;
        el.addEventListener('keydown', (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                el.click();
            } else if (e.key === " ") {
                e.preventDefault();
            }   
        })
        el.addEventListener('keyup', (e) => {
            if (e.key === " ") {
                e.preventDefault();
                el.click();
            }
        })
    }
}

function loadPlaylistsList() {
    fetch("/get-playlists")
    .then((response) => response.json())
    .then((data) => {
    data.playlists.sort();
    data.playlists.forEach((filename) => {
        let option = document.createElement("div");
        option.className = "deck-item";
        option.setAttribute("data-val", filename);
        option.textContent = filename.replace(/\.[a-zA-Z0-9]+$/, '');
        option.addEventListener('click', (e) => {
            toggleTextEl.textContent = e.target.getAttribute("data-val").replace(/\.[a-zA-Z0-9]+$/, '');
            deckName = e.target.getAttribute("data-val");
            optionsDropdownEl.style.display = 'none';
            toggleDropdownEl.classList.remove('open');
        })
        option.tabIndex = 0;
        option.addEventListener('keydown', (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                option.click();
            } else if (e.key === " ") {
                e.preventDefault();
            }   
        })
        option.addEventListener('keyup', (e) => {
            if (e.key === " ") {
                e.preventDefault();
                option.click();
            }
        })
        optionsDropdownEl.appendChild(option);
    });
    })
    .catch((error) => console.error("Error:", error));
}

function showHelp() {
    helpEl.style.display = "block";
    menuEl.style.display = "none";
}

function hideHelp() {
    helpEl.style.display = "none";
    menuEl.style.display = "block";
}

loadPlaylistsList();
addTabs();