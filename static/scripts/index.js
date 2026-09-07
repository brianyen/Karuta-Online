let roomCodeEl = document.getElementById("room-code-input");
let helpEl = document.getElementById("help-popup");
let menuEl = document.getElementById("index-menu");
let playlistSelectEl = document.getElementById("playlist-select");

roomCodeEl.addEventListener("input", (event) => {
    event.target.value = event.target.value.toUpperCase();
})

function sendCreateRequest() {
    let deckName = playlistSelectEl.value;
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
    playlistSelectEl.innerHTML = "";
    data.playlists.sort();
    data.playlists.forEach((filename) => {
        let option = document.createElement("option");
        option.value = filename;
        option.textContent = filename.replace(/\.[a-zA-Z0-9]+$/, '');;
        playlistSelectEl.appendChild(option);
    });
    })
    .catch((error) => console.error("Error:", error));
}

function showHelp() {
    console.log("showing help")
    helpEl.style.display = "block";
    menuEl.style.display = "none";
}

function hideHelp() {
    console.log("hiding help")
    helpEl.style.display = "none";
    menuEl.style.display = "block";
}

loadPlaylistsList();
addTabs();