const state = {
  environmentId: "ENV-C8-1-PROTOTIPO-MOCK",
  rotation: 0,
};

const screens = [...document.querySelectorAll("[data-screen]")];
const environmentInput = document.querySelector("#environment");
const reviewEnvironment = document.querySelector("#review-environment");
const reviewRotation = document.querySelector("#review-rotation");

function showScreen(name) {
  screens.forEach((screen) => {
    screen.classList.toggle("hidden", screen.dataset.screen !== name);
  });
}

function refreshReview() {
  state.environmentId = environmentInput.value;
  reviewEnvironment.textContent = state.environmentId;
  reviewRotation.textContent = String(state.rotation);
}

document.addEventListener("click", (event) => {
  const rotationButton = event.target.closest("[data-rotation]");
  if (rotationButton) {
    state.rotation = Number(rotationButton.dataset.rotation);
    document.querySelectorAll("[data-rotation]").forEach((button) => {
      button.classList.toggle("selected", button === rotationButton);
    });
    refreshReview();
    return;
  }

  const nextButton = event.target.closest("[data-next]");
  if (!nextButton) {
    return;
  }

  refreshReview();
  showScreen(nextButton.dataset.next);
});

environmentInput.addEventListener("input", refreshReview);
refreshReview();
