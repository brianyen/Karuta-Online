let audioPlayerEl = document.getElementById("audioPlayer");
let dummyAudioPlayerEl = document.getElementById("dummyAudioPlayer");
let gameSpaceOpponentEl = document.getElementById("game-space-opponent");
let gameSpaceSelfEl = document.getElementById("game-space-self");
let readyEl = document.getElementById("readyCheckbox");
let readyButtonEl = document.getElementById("ready");
let readyDivEl = document.getElementById("readyDiv");
let tapoutEl = document.getElementById("tapout")
let tapoutDivEl = document.getElementById("tapoutDiv")
let deckDisplayEl = document.getElementById("deckDisplay");
let nextGameDivEl = document.getElementById("nextGameDiv")
let countdownEl = document.getElementById("countdown");
let answerEl = document.getElementById("answer");
let ownScoreEl = document.getElementById("own-score");
let otherScoreEl = document.getElementById("other-score");
let notificationsEl = document.getElementById("notifications");
let playlistSelectEl = document.getElementById("playlistSelect");
let volumeEl = document.getElementById("volume-slider");

let images = {};
let mapping = {};

let correct = true;
let dragged = null;
let songStart = null;
let faultedSelf = -1;
let faultedOpponent = -1;
let wrongCards = [];
let timeoutActive = false;

let params = new URLSearchParams(document.location.search);
let room_key = params.get("room"); 
let deck;
let audioContext = new (window.AudioContext || window.webkitAudioContext)();
let gainControl = audioContext.createGain()
let currentSongBuff = null;
let currentNode = null;
let currentSong = "";
let correctSide = "";
let nextRoom = ""
let init = false;

let ownScore = -1; // eventually replace with tracking full card decks i think
let otherScore = -1;

let playerID = sessionStorage.getItem("playerID") || crypto.randomUUID();
sessionStorage.setItem("playerID", playerID);
const socket = io();
gainControl.gain.value = parseFloat(volumeEl.value);
gainControl.connect(audioContext.destination);

socket.on('connect', () => {
    console.log("Connection established");
    socket.emit('join_game', { room: room_key, player_id: playerID })
});

socket.on('1p_room', (e) => {
    deck = e.deck.replace(/\.[a-zA-Z0-9]+$/, '');
    loadCustom();
    deckDisplayEl.innerHTML = "Deck: " + deck;
});

socket.on('2p_room', (e) => {
    tapoutDivEl.style.display = "none";
    tapoutEl.disabled = false;
    correct = true;
    readyDivEl.style.display = "block";

    if (!timeoutActive) {
        readyButtonEl.disabled = false;
    }

    if (!init) {
        initGameState(e);
    }
    init = true;
});

socket.on('start_sync', (e) => {
    startSyncHandler(e)
});

socket.on('start_playing', (e) => {
    countdown.innerHTML = "Round starting in 3...";
    console.log(`output latency: ${audioContext.outputLatency}`);
    console.log(`base latency: ${audioContext.baseLatency}`);

    updateLogs(`Starting countdown at ${Date.now()}`)

    setTimeout(() => {
        countdown.innerHTML = "Round starting in 2..."
    }, 1000)

    setTimeout(() => {
        countdown.innerHTML = "Round starting in 1..."
    }, 2000)

    async function thirdTimeoutHandler() {
        if (!currentSongBuff) {
            console.error("Error: Song buffer isn't prepared, retrying in 500ms");
            setTimeout(thirdTimeoutHandler, 500);
        }
        countdownEl.innerHTML = "Round Started"
        currentSong = e.song;

        currentNode = audioContext.createBufferSource();
        currentNode.buffer = currentSongBuff;
        currentNode.connect(gainControl);
        currentNode.start(audioContext.currentTime, e.start_time);

//         let playConfirm = await playSong(currentSong, e.start_time, e.audio_url)
        readyDivEl.style.display = 'none';
        readyEl.checked = false;
        tapoutDivEl.style.display = 'block';
        tapoutEl.disabled = false;
        correct = false;
        faultedSelf = -1;
        faultedOpponent = -1;
        songStart = Date.now();
        updateLogs(`Song actually started at ${songStart}`);
        answerEl.innerHTML = "Now playing...";

        let card = document.getElementById(currentSong);
        if (card != null) {
            correctSide = card.parentElement.id;
        } else {
            correctSide = "";
        }
    }

    setTimeout(thirdTimeoutHandler, 3000);
});

socket.on('round_results', (e) => {
    console.log("Handling round results")
    let winner = e.winner;
    let remove = e.remove;
    let add = e.add;

    faultCount = 0;
    if (faultedSelf == 1) {
        faultCount++;
    }
    if (faultedOpponent == 1) {
        faultCount++;
    }
    if (faultCount == 0) {
        faultCount = -1;
    }

    let target = (remove === "") ? null : document.getElementById(remove);
    let faultParams = { fault_status: faultCount, player_id: playerID, room: room_key };

    countdownEl.innerHTML = "Round is finished"
    answerEl.innerHTML = "Song name: " + currentSong;
    
    if (target != null && winner === "") {
        addNextCard(target, add, faultParams).then((res) => {
            if (!res) {
                target.removeEventListener("click", handleSongChoice);
                target.innerHTML = "";
                target.style.borderColor = "white";
                target.style.cursor = "auto";
                target.id = "";
                target.draggable = false;
                if (target.parentElement.id == "game-space-self") {
                    ownScore--;
                } else {
                    otherScore--;
                }
                updateScores();
            }
        });
    } else if (target != null) {
        target.removeEventListener("click", handleSongChoice);
        target.innerHTML = "";
        target.style.borderColor = "white";
        target.style.cursor = "auto";
        target.id = "";
        target.draggable = false;
    }

    socket.emit('fault_msg', faultParams);
    let displayTitle = mapping[currentSong] || currentSong;
    if (winner === playerID) {
        ownScore--;
        updateLogs("RESULT: You won the card " + displayTitle);
    } else if (winner === "") {
        if (remove != "" && add != "") {
            let addDisplayTitle = mapping[add] || add;
            updateLogs("REROLL: You rerolled " + displayTitle + " into " + addDisplayTitle);
        } else if (remove != "") {
            updateLogs("REROLL: You rerolled " + displayTitle + " with no dead cards remaining");
        } else {
            updateLogs("DEAD CARD: " + displayTitle);
        }
    } else {
        otherScore--;
        updateLogs("RESULT: Opponent won the card " + displayTitle);
    }

    wrongCards.forEach(card => {
        card.style.outline = "";
        card.style.outlineOffset = "";
    })

    updateScores();

    correct = true;
    tapoutEl.disabled = true;

    faultedSelf = -1;
    faultedOpponent = -1;
})

socket.on('fault_response', (e) => {
    console.log("Handling faults")
    let displayName = mapping[currentSong] || currentSong;
    Object.keys(e.args).forEach(key => {
        // deal with this later later
        if (key === playerID) { // needs to be card replacement later on
            if (e.args[key] == 1) {
                updateLogs("FAULT: You faulted when " + displayName + " was playing.");
                ownScore += 1;
                otherScore -= 1;
            } else if (e.args[key] == 2) {
                updateLogs("FAULT: You faulted twice when " + displayName + " was playing.");
                ownScore += 2;
                otherScore -= 2;
            }
        } else {
            if (e.args[key] == 1) {
                updateLogs("FAULT: Opponent faulted when " + displayName + " was playing.");
                ownScore -= 1;
                otherScore += 1;
            } else if (e.args[key] == 2) {
                updateLogs("FAULT: Opponent faulted twice when " + displayName + " was playing.");
                ownScore -= 2;
                otherScore += 2;
            }
        } 
        updateScores();
    })
})

socket.on('re_emission', (e) => {
    console.log("Entering re-emission")
    if (init) {
        return;
    }
    deck = e.deck.replace(/\.[a-zA-Z0-9]+$/, '');
    countdownEl.innerHTML = "Round Started"
    readyDivEl.style.display = 'none';
    readyEl.checked = false;
    tapoutDivEl.style.display = 'block';
    correct = true;
    faultedSelf = -1;
    faultedOpponent = -1;
    answerEl.innerHTML = "Now playing..."
    socket.emit('sync_ready', { room: room_key, player_id: playerID })
    tapOut();
})

socket.on('game_finished', (e) => {
    if (e.winner === playerID) {
        countdownEl.innerHTML = "Game is finished! You won.";
    } else if (e.winner === "") {
        countdownEl.innerHTML = "Game is finished!";
    } else {
        countdownEl.innerHTML = "Game is finished! You lost."
    }
    readyDivEl.style.display = 'none';
    tapoutDivEl.style.display = 'none';
    nextGameDivEl.style.display = 'block';
    nextRoom = e.next_code;
})

socket.on('room_missing', () => [
    alert("attempted to join nonexistent or invalid room")
])

socket.on('room_full', () => {
    alert("issue while joining room, it may be full")
})

socket.on('ping_check', (server_callback) => { server_callback(); })

async function startSyncHandler(e) {
    try {
        readyButtonEl.disabled = true;
        countdown.innerHTML = "Syncing audio tracks..."
        
        if (currentNode) {
            currentNode.stop();
            currentNode.disconnect();
            currentNode = null;
        }

        const response = await fetch(e.audio_url);
        const buff = await response.arrayBuffer();
        currentSongBuff = await audioContext.decodeAudioData(buff);
        socket.emit('sync_ready', { room: room_key, player_id: playerID });
        /*
        const blob = await response.blob();
        const localAudioUrl = URL.createObjectURL(blob);
        audioPlayerEl.oncanplaythrough = () => {
            socket.emit('sync_ready', { room: room_key, player_id: playerID });
            audioPlayerEl.oncanplaythrough = null;
        }
        audioPlayerEl.src = localAudioUrl; 
        audioPlayerEl.load();*/
    } catch (e) {
        console.error("Error: " + e)
    }
}

async function playSong(song, randomStart) {
    async function attemptPlayback() {
        await audioPlayerEl.play().catch((error) => {
            console.warn("Playback failed (promise rejection), retrying...", error);
            setTimeout(attemptPlayback, 500);
        });
    }
    audioPlayerEl.currentTime = randomStart;

    await attemptPlayback();
        
    audioPlayerEl.onerror = function () {
        console.warn("Audio error event fired, retrying playback...");
        setTimeout(attemptPlayback, 500);
    };
}

function handleSongChoice(event) {
    if (correct) {
        return;
    }
    let target = (event.target.id === "") ? event.target.parentElement : event.target;
    chosenTitle = target.id;

    if (currentSong === chosenTitle) {
        correct = true;
        target.removeEventListener("click", handleSongChoice);
        target.innerHTML = "";
        target.style.borderColor = "white";
        target.style.cursor = "auto";
        target.id = "";
        target.draggable = false;

        let timeClicked = Date.now()
        let timeForCard = Math.round(timeClicked - songStart); 

        countdownEl.innerHTML = "Waiting for round results..."
        socket.emit('player_response', { player_id: playerID, room: room_key, response_time: timeForCard });
        updateLogs(`TIME: You took ${timeForCard}ms to click on ${currentSong}`)
        canTapOut = false;
        tapoutEl.disabled = true;
    } else if (!correct) {
        wrongCards.push(target);
        target.style.outline = "2px solid red";
        target.style.outlineOffset = "-2px";
        if (target.parentElement.id != correctSide) {
            if (target.parentElement.id == "game-space-self") {
                faultedSelf = 1;
            } else if (target.parentElement.id == "game-space-opponent") {
                faultedOpponent = 1;
            }
        }
    }
}

function addNextCard(toReplace = null, nextCardTitle = null, faultParams = {}) {
    return new Promise((resolve) => {
        if (nextCardTitle === "") {
            resolve(false);
            return;
        }

        toReplace.style.outline = "4px solid red";
        toReplace.style.outlineOffset = "-4px";
        readyButtonEl.disabled = true;
        correct = true;
        timeoutActive = true;
        setTimeout(() => {
            toReplace.parentElement.replaceChild(createCardElement(nextCardTitle), toReplace);
            let next = document.getElementById(nextCardTitle);
            toReplace.style.outline = "4px solid red";
            toReplace.style.outlineOffset = "-4px";
            setTimeout(() => {
                toReplace.style.outline = "";
                toReplace.style.outlineOffset = "";
                readyButtonEl.disabled = false;
                timeoutActive = false;
                resolve(true);
            }, 1500);
        }, 1500);
    });
}

function createCardElement(songTitle) {
    let songCard = document.createElement("div");

    let cardImage = document.createElement("img");
    let cardText = document.createElement("canvas");
    songCard.appendChild(cardImage);
    songCard.appendChild(cardText);
        
    songCard.className = "card";
    songCard.id = songTitle;
    cardImage.className = "card-image";
    cardText.className = "card-text";
    cardImage.draggable = false;
    songCard.draggable = true;

    cardText.height = 72;
    cardText.width = 104;
    
    let cardTitle = (mapping[songTitle] != undefined) ? mapping[songTitle] : songTitle;

    songCard.addEventListener("click", handleSongChoice);

    songCard.addEventListener("dragenter", (event) => {
        event.preventDefault()
        if (correct && dragged != null && songCard.parentElement == gameSpaceSelfEl) {
            const draggedElementId = event.dataTransfer.getData("text/plain");
            songCard.style.outline = "4px solid #6fb5cf";
            songCard.style.outlineOffset = "-4px";
        }
    });

    songCard.addEventListener("dragover", (event) => {
        event.preventDefault();
    })

    songCard.addEventListener("dragleave", (event) => {
        if (correct && dragged != null && !songCard.contains(event.relatedTarget)) {
            songCard.style.outline = "";
            songCard.style.outlineOffset = "";
        }
    });

    songCard.addEventListener("dragstart", (event) => {
        if (correct) {
            dragged = event.target;
        }
    });

    songCard.addEventListener("dragend", (event) => {
        if (correct) {
            dragged = null;
        }
    });

    songCard.addEventListener("drop", (event) => {
        songCard.style.outline = "";
        songCard.style.outlineOffset = "";

        if (correct && dragged && dragged.id != event.target.parentElement.id && dragged.id != event.target.id && 
                event.target.parentElement == gameSpaceSelfEl && dragged.parentElement == gameSpaceSelfEl) {
            let dummy = createCardElement("");
            gameSpaceSelfEl.replaceChild(dummy, dragged);
            gameSpaceSelfEl.replaceChild(dragged, songCard);
            gameSpaceSelfEl.replaceChild(songCard, dummy);
        }
    });

    let context = cardText.getContext("2d");
    context.font = "bold 12px Arial";
    context.fillStyle = "black";
    context.textAlign = "center";
    context.textBaseline = "top";
    context.shadowBlur = 0.001; 
    context.shadowColor = 'transparent';
    if (cardTitle.slice(-4) === ".mp3") {
        cardTitle = cardTitle.slice(0, -4);
    } 
    addWrappedCanvasText(context, cardTitle, cardText.width / 2, 20, cardText.width - 10, 14);
    cardImage.src = images[songTitle] || "";

    return songCard;
}

async function loadCustom() {
    return new Promise((resolve) => {
        fetch("/get-mapping?filename=" + deck + ".json")
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.log("No custom text");
            } else {
                mapping = data;
            }

            fetch("/get-images?filename=" + deck + ".json")
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                console.log("No custom images")
                resolve(true);
                } else {
                Object.keys(data).forEach((k) => {
                    images[k] = data[k];
                })
                resolve(true);
                }
            });
        });
    })
}

function toggleReady() {
    let checkedStatus = !readyEl.checked;
    readyEl.checked = checkedStatus;
    if (checkedStatus) {
        socket.emit('player_ready', { player_id: playerID, room: room_key });
    } else {
        socket.emit('player_unready', { player_id: playerID, room: room_key });
    }

    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }

    /*let silent = "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";
    dummyAudioPlayerEl.src = silent;
    dummyAudioPlayerEl.volume = 0;
    dummyAudioPlayerEl.play().then(() => {
        dummyAudioPlayerEl.pause();
    }).catch(err => {
        console.error("silent audio fail:", err);
    });*/
}

function tapOut() {
    correct = true;
    countdownEl.innerHTML = ("Waiting for round results...")
    socket.emit('player_response', { player_id: playerID, room: room_key, response_time: -2 })
    tapoutEl.disabled = true;
}

function confirmNavigation(e) {
    if (
        e.ctrlKey ||
        e.metaKey ||
        e.shiftKey ||
        e.altKey ||
        e.button !== 0
    ) {
        return;
    }

    res = confirm("Are you sure you want to leave the room?");
    if (res) {
        socket.emit('leave_room', { room: room_key, player_id: playerID });
    }
    return res;
}

function updateScores() {
    ownScoreEl.innerHTML = "You: " + ownScore;
    otherScoreEl.innerHTML = "Opponent: " + otherScore;
}

function updateLogs(newEntry) {
    notificationsEl.innerHTML += (newEntry + "<br/>");
    notificationsEl.scrollTop = notificationsEl.scrollHeight;
}

async function initGameState(e) {
    deck = e.deck.replace(/\.[a-zA-Z0-9]+$/, '');
    let res = await loadCustom();
    deckDisplayEl.innerHTML = "Deck: " + deck;
    const arraysEqual = (a, b) => a.length === b.length && a.every((val, index) => val === b[index]);
    Object.keys(e.songs).forEach((id) => {
        if (id === playerID) {
            e.songs[id].forEach((song) => {
                gameSpaceSelfEl.appendChild(createCardElement(song));
            })
        } else {
            e.songs[id].forEach((song) => {
                gameSpaceOpponentEl.appendChild(createCardElement(song));
            })
        }
    })
    Object.keys(e.scores).forEach((id) => {
        if (id === playerID) {
            ownScore = e.scores[id];
        } else {
            otherScore = e.scores[id];
        }
    });
    updateScores();
}

function replayRoom() {
    if (nextRoom === "") {
        console.log("Attempting to replay but the next room's code is not found")
        return;
    }
    let deckName = playlistSelectEl.value
    fetch("/replay-room-rq", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ deck: deckName, code: nextRoom })
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

function addWrappedCanvasText(context, text, x, y, widthLimit, yOffset) {
    let wordArray = text.split(" ")
    let currentLine = "";

    for (let i = 0; i < wordArray.length; i++) {
        let test = currentLine + wordArray[i] + " ";
        let projectedWidth = context.measureText(test).width;

        if (projectedWidth > widthLimit && currentLine != "") {
            context.fillText(currentLine.trim(), x, y);
            currentLine = wordArray[i] + " ";
            y += yOffset;
        } else {
            currentLine = test;
        }
    }
    context.fillText(currentLine.trim(), x, y);
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

volumeEl.addEventListener("change", (e) => {
    gainControl.gain.setTargetAtTime(parseFloat(e.target.value), audioContext.currentTime, 0.1);
})

loadPlaylistsList();