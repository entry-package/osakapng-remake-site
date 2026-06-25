const menuButton = document.querySelector(".menu-toggle");
const nav = document.querySelector(".site-nav");

menuButton?.addEventListener("click", () => {
  const isOpen = document.body.classList.toggle("menu-open");
  menuButton.setAttribute("aria-expanded", String(isOpen));
});

nav?.addEventListener("click", (event) => {
  if (event.target instanceof HTMLAnchorElement) {
    document.body.classList.remove("menu-open");
    menuButton?.setAttribute("aria-expanded", "false");
  }
});

const filterButtons = document.querySelectorAll("[data-filter]");
const talentCards = document.querySelectorAll(".talent-card");

filterButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const filter = button.getAttribute("data-filter");
    filterButtons.forEach((item) => item.classList.toggle("active", item === button));
    talentCards.forEach((card) => {
      const visible = filter === "all" || card.getAttribute("data-kind") === filter;
      card.classList.toggle("is-hidden", !visible);
    });
  });
});

const form = document.querySelector(".contact-form");
const note = document.querySelector(".form-note");

form?.addEventListener("submit", (event) => {
  event.preventDefault();
  if (!(form instanceof HTMLFormElement)) return;
  if (!form.checkValidity()) {
    form.reportValidity();
    return;
  }
  if (note) {
    note.textContent = "送信前確認の試作です。本番化時にフォーム送信先を接続します。";
  }
});
