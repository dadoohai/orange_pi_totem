const environments = {
  "loja-a": {
    name: "Ambiente Loja A - TESTE",
    environmentId: "ENV-MOCK-LOJA-A",
  },
  recepcao: {
    name: "Ambiente Recepcao - TESTE",
    environmentId: "ENV-MOCK-RECEPCAO",
  },
  vitrine: {
    name: "Ambiente Vitrine - TESTE",
    environmentId: "ENV-MOCK-VITRINE",
  },
};

const state = {
  environmentMode: "mock",
  environmentKey: "loja-a",
  manualEnvironmentId: "ENV-MOCK-MANUAL-BANCADA",
  rotation: 0,
};

const screens = [...document.querySelectorAll("[data-screen]")];
const manualBox = document.querySelector(".manual-box");
const manualInput = document.querySelector("#environment");
const manualToggle = document.querySelector("[data-toggle-manual]");
const reviewEnvironment = document.querySelector("#review-environment");
const reviewEnvironmentId = document.querySelector("#review-environment-id");
const reviewRotation = document.querySelector("#review-rotation");
const readyEnvironment = document.querySelector("#ready-environment");
const readyRotation = document.querySelector("#ready-rotation");

function showScreen(name) {
  screens.forEach((screen) => {
    screen.classList.toggle("hidden", screen.dataset.screen !== name);
  });
}

function selectedEnvironment() {
  if (state.environmentMode === "manual") {
    return {
      name: "Ambiente manual - TESTE",
      environmentId: state.manualEnvironmentId,
    };
  }
  return environments[state.environmentKey] || environments["loja-a"];
}

function refreshReview() {
  if (manualInput) {
    state.manualEnvironmentId = manualInput.value;
  }
  const environment = selectedEnvironment();
  reviewEnvironment.textContent = environment.name;
  reviewEnvironmentId.textContent = `ID tecnico de teste: ${environment.environmentId}`;
  reviewRotation.textContent = String(state.rotation);
  readyEnvironment.textContent = environment.name;
  readyRotation.textContent = String(state.rotation);
}

document.addEventListener("click", (event) => {
  const environmentButton = event.target.closest("[data-environment-key]");
  if (environmentButton) {
    state.environmentMode = "mock";
    state.environmentKey = environmentButton.dataset.environmentKey;
    document.querySelectorAll("[data-environment-key]").forEach((button) => {
      button.classList.toggle("selected", button === environmentButton);
    });
    manualBox.classList.add("hidden");
    manualToggle.textContent = "Inserir codigo manualmente (avancado)";
    refreshReview();
    return;
  }

  const rotationButton = event.target.closest("[data-rotation]");
  if (rotationButton) {
    state.rotation = Number(rotationButton.dataset.rotation);
    document.querySelectorAll("[data-rotation]").forEach((button) => {
      button.classList.toggle("selected", button === rotationButton);
    });
    refreshReview();
    return;
  }

  if (event.target.closest("[data-toggle-manual]")) {
    state.environmentMode = state.environmentMode === "manual" ? "mock" : "manual";
    manualBox.classList.toggle("hidden", state.environmentMode !== "manual");
    manualToggle.textContent =
      state.environmentMode === "manual" ? "Usar lista de ambientes" : "Inserir codigo manualmente (avancado)";
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

manualInput.addEventListener("input", refreshReview);
refreshReview();
