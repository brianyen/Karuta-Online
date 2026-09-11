let tableEl = document.getElementById("deck-table");
let playlistSelectDivEl = document.getElementById("playlist-select-div");
let toggleDropdownEl = document.querySelector(".toggle-dropdown");
let optionsDropdownEl = document.querySelector(".options-dropdown");
let deckFilterEl = document.getElementById("deck-filter");
let toggleTextEl = document.getElementById("toggle-text");
let deckName = null;

document.addEventListener("click", (event) => {
    if (!playlistSelectDivEl.contains(event.target)) {
        optionsDropdownEl.style.display = "none";
        toggleDropdownEl.classList.remove('open');
    }
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

function sendHome() {
    fetch("/", {
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

function loadPlaylistsList() {
    fetch("/get-playlists")
    .then((response) => response.json())
    .then((data) => {
        data.playlists.sort();
        data.playlists.forEach((filename) => {
            if (deckName == null) {
                deckName = filename;
            }
            toggleTextEl.textContent = filename.replace(/\.[a-zA-Z0-9]+$/, '');
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
            optionsDropdownEl.appendChild(option);
        });
    })
    .catch((error) => console.error("Error:", error));
}

function loadDeck() {
    if (deckName == null || deckName === "") {
        console.error("No deck selected from dropdown menu");
        return;
    }

    let toRemove = [];
    for (child of tableEl.children) {
        if (child.id != "") {
            toRemove.push(child);
        }
    }

    for (node of toRemove) {
        tableEl.removeChild(node);
    }

    fetch(`/load-playlist?filename=${encodeURIComponent(deckName)}`)
    .then(response => {
        return response.json()
    })
    .then(data => {
        if (data.songs == null) {
            console.error("Didn't receive any songs from server");
        }
        data.songs.sort();
        for (let song of data.songs) {
            let row = document.createElement("tr");
            row.id = song;

            let c1 = document.createElement("td");
            c1.className = "fileName";
            let c2 = document.createElement("td");
            c2.className = "displayTitle";
            let c3 = document.createElement("td");
            c3.className = "cardImage";

            c1.innerHTML = song;
            
            row.appendChild(c1);
            row.appendChild(c2);
            row.appendChild(c3);
            tableEl.appendChild(row);
        }

        loadCustom(deckName);
    })
}

async function loadCustom(deckName) {
    return new Promise((resolve) => {
        fetch(`/get-mapping?filename=${encodeURIComponent(deckName)}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.log("No custom text");
            }

            for (let originalName of Object.keys(data)) {
                let row = document.getElementById(originalName);
                
                try {
                    let cell = row.getElementsByClassName("displayTitle")[0];
                    cell.innerHTML = data[originalName];
                } catch {
                    console.log("cell removed before it could be filled in");
                }
            }

            fetch(`/get-images?filename=${encodeURIComponent(deckName)}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.log("No custom images");
                    resolve(true);
                } else {
                    Object.keys(data).forEach((k) => {
                        let row = document.getElementById(k);
                        try {
                            let cell = row.getElementsByClassName("cardImage")[0];
                            let img = document.createElement("img");
                            img.style.width = "100px";
                            img.style.height = "100px";
                            img.src = data[k];
                            cell.appendChild(img);
                        } catch {
                            console.log("cell removed before it couldbe filled in");
                        }
                    })
                }
            });
        });
    })
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

loadPlaylistsList();
addTabs();