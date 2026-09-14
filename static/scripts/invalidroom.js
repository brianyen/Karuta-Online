function sendHome() {
    if (
        e.ctrlKey ||
        e.metaKey ||
        e.shiftKey ||
        e.altKey ||
        e.button !== 0
    ) {
        return;
    }

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