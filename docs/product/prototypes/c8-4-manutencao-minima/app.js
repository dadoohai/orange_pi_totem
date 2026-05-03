const screens = [...document.querySelectorAll("[data-screen]")];
const resetConfirmation = document.querySelector("#reset-confirmation");
const resetButton = document.querySelector('[data-maintenance-result="reset"]');
const resultTitle = document.querySelector("#result-title");
const resultMessage = document.querySelector("#result-message");

function showScreen(name) {
  screens.forEach((screen) => {
    screen.classList.toggle("hidden", screen.dataset.screen !== name);
  });
}

function showResult(kind) {
  if (kind === "reset") {
    resultTitle.textContent = "Limpeza de configuracao simulada";
    resultMessage.textContent = "Nenhuma configuracao real foi apagada.";
  } else {
    resultTitle.textContent = "Reinicio de exibicao simulado";
    resultMessage.textContent = "Nenhum player, MPV ou servico foi reiniciado.";
  }
  if (resetConfirmation) {
    resetConfirmation.checked = false;
    resetButton.disabled = true;
  }
  showScreen("result");
}

document.addEventListener("click", (event) => {
  const maintenanceButton = event.target.closest("[data-maintenance-result]");
  if (maintenanceButton) {
    showResult(maintenanceButton.dataset.maintenanceResult);
    return;
  }

  const nextButton = event.target.closest("[data-next]");
  if (!nextButton) {
    return;
  }
  showScreen(nextButton.dataset.next);
});

resetConfirmation.addEventListener("change", () => {
  resetButton.disabled = !resetConfirmation.checked;
});
