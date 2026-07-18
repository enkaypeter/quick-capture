/**
 * Simon on the Streets - Quick Capture MVP
 * Core client-side functionality:
 * - Geolocation + What3Words conversion
 * - Voice note recording
 * - Flash message auto-dismiss
 */

(function () {
  "use strict";

  // ─── Flash messages: auto-dismiss after 5s ───────────────────────────
  document.querySelectorAll(".flash-msg").forEach(function (el) {
    setTimeout(function () {
      el.style.transition = "opacity 0.3s";
      el.style.opacity = "0";
      setTimeout(function () {
        el.remove();
      }, 300);
    }, 5000);
  });

  // ─── Geolocation: Share my location ──────────────────────────────────
  var shareBtn = document.getElementById("share-location-btn");
  var locationInput = document.getElementById("location_search");
  var latInput = document.getElementById("location_lat");
  var lngInput = document.getElementById("location_lng");
  var locationStatus = document.getElementById("location-status");

  if (shareBtn) {
    shareBtn.addEventListener("click", function () {
      if (!navigator.geolocation) {
        showLocationStatus("Geolocation is not supported by your browser.", true);
        return;
      }

      showLocationStatus("Getting your location...", false);
      shareBtn.disabled = true;

      navigator.geolocation.getCurrentPosition(
        function (position) {
          var lat = position.coords.latitude;
          var lng = position.coords.longitude;

          latInput.value = lat;
          lngInput.value = lng;

          // Convert to What3Words
          convertToWhat3Words(lat, lng);
        },
        function (error) {
          shareBtn.disabled = false;
          switch (error.code) {
            case error.PERMISSION_DENIED:
              showLocationStatus("Location permission denied.", true);
              break;
            case error.POSITION_UNAVAILABLE:
              showLocationStatus("Location unavailable.", true);
              break;
            case error.TIMEOUT:
              showLocationStatus("Location request timed out.", true);
              break;
            default:
              showLocationStatus("An unknown error occurred.", true);
          }
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    });
  }

  function convertToWhat3Words(lat, lng) {
    // What3Words API integration
    // NOTE: In production, this should go through your backend to protect the API key
    var apiKey = window.W3W_API_KEY || "";

    if (!apiKey) {
      // Fallback: just show coordinates and generate a placeholder w3w-style address
      var placeholder = generatePlaceholderW3W(lat, lng);
      locationInput.value = placeholder;
      showLocationStatus(
        "Location captured (" + lat.toFixed(4) + ", " + lng.toFixed(4) + ")",
        false
      );
      if (shareBtn) shareBtn.disabled = false;
      return;
    }

    // we will have to fetch this from the backend server
    fetch(
      "https://api.what3words.com/v3/convert-to-3wa?coordinates=" +
        lat +
        "%2C" +
        lng +
        "&key=" +
        apiKey
    )
      .then(function (response) {
        return response.json();
      })
      .then(function (data) {
        if (data.words) {
          locationInput.value = data.words;
          showLocationStatus("Location: ///" + data.words, false);
        } else {
          locationInput.value = generatePlaceholderW3W(lat, lng);
          showLocationStatus("W3W lookup failed, coordinates saved.", true);
        }
      })
      .catch(function () {
        locationInput.value = generatePlaceholderW3W(lat, lng);
        showLocationStatus("W3W lookup failed, coordinates saved.", true);
      })
      .finally(function () {
        if (shareBtn) shareBtn.disabled = false;
      });
  }

  function generatePlaceholderW3W(lat, lng) {
    // Generate a deterministic placeholder when W3W API is unavailable
    return lat.toFixed(5) + "," + lng.toFixed(5);
  }

  function showLocationStatus(message, isError) {
    if (!locationStatus) return;
    locationStatus.textContent = message;
    locationStatus.classList.remove("hidden", "text-red-500", "text-gray-500");
    locationStatus.classList.add(isError ? "text-red-500" : "text-gray-500");
  }

  // ─── Voice Note Recording ────────────────────────────────────────────
  var recordBtn = document.getElementById("record-btn");
  var voicePlayback = document.getElementById("voice-playback");
  var audioPlayback = document.getElementById("audio-playback");
  var voiceNoteInput = document.getElementById("voice_note");

  var mediaRecorder = null;
  var audioChunks = [];
  var isRecording = false;

  if (recordBtn) {
    recordBtn.addEventListener("click", function () {
      if (!isRecording) {
        startRecording();
      } else {
        stopRecording();
      }
    });
  }

  function startRecording() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      alert("Audio recording is not supported in this browser.");
      return;
    }

    navigator.mediaDevices
      .getUserMedia({ audio: true })
      .then(function (stream) {
        mediaRecorder = new MediaRecorder(stream);
        audioChunks = [];

        mediaRecorder.addEventListener("dataavailable", function (event) {
          audioChunks.push(event.data);
        });

        mediaRecorder.addEventListener("stop", function () {
          var audioBlob = new Blob(audioChunks, { type: "audio/webm" });
          var audioUrl = URL.createObjectURL(audioBlob);

          // Show playback
          audioPlayback.src = audioUrl;
          voicePlayback.classList.remove("hidden");

          // Create a File from the Blob and attach to the hidden file input
          var file = new File([audioBlob], "voice_note.webm", {
            type: "audio/webm",
          });
          var dt = new DataTransfer();
          dt.items.add(file);
          voiceNoteInput.files = dt.files;

          // Stop all tracks
          stream.getTracks().forEach(function (track) {
            track.stop();
          });
        });

        mediaRecorder.start();
        isRecording = true;
        recordBtn.innerHTML =
          '<svg class="w-4 h-4 text-red-500 animate-pulse" fill="currentColor" viewBox="0 0 20 20"><circle cx="10" cy="10" r="6"/></svg> Stop Recording';
        recordBtn.classList.add("border-red-300", "text-red-600");
        recordBtn.classList.remove("border-gray-300", "text-gray-700");
      })
      .catch(function (err) {
        alert("Could not access microphone: " + err.message);
      });
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    isRecording = false;
    recordBtn.innerHTML =
      '<svg class="w-4 h-4 text-gray-500" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clip-rule="evenodd"/></svg> Re-record';
    recordBtn.classList.remove("border-red-300", "text-red-600");
    recordBtn.classList.add("border-gray-300", "text-gray-700");
  }
})();
