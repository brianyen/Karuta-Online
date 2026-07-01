let roomCodeEl = document.getElementById("room-code-input");
let playlistSelectEl = document.getElementById("playlistSelect");

roomCodeEl.addEventListener("input", (event) => {
    event.target.value = event.target.value.toUpperCase();
})

function sendCreateRequest() {
    let deckName = playlistSelectEl.value
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

function loadPlaylistsList() {
    fetch("/get-playlists")
    .then((response) => response.json())
    .then((data) => {
    playlistSelectEl.innerHTML = "";
    data.playlists.forEach((filename) => {
        let option = document.createElement("option");
        option.value = filename;
        option.textContent = filename;
        playlistSelectEl.appendChild(option);
    });
    })
    .catch((error) => console.error("Error:", error));
}

loadPlaylistsList();