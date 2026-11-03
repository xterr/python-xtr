/* The copy button of the command on the home page. */

/*
 * document$ emits once for the first page and again after every instant page
 * change. The hero is inside the part of the document that an instant change
 * replaces, so the button is a new element each time and is bound again here.
 */
document$.subscribe(function () {
  var button = document.querySelector("[data-xtr-copy]")
  if (!button) {
    return
  }

  var source = document.getElementById(button.dataset.xtrCopy)
  if (!source) {
    return
  }

  var timer = null
  button.addEventListener("click", function () {
    var text = source.textContent.trim()

    /* The clipboard needs a secure context. Without one the button does
       nothing visible, which is better than an error in the console. */
    if (!navigator.clipboard) {
      return
    }

    navigator.clipboard.writeText(text).then(function () {
      button.classList.add("xtr-hero__copy--done")
      window.clearTimeout(timer)
      timer = window.setTimeout(function () {
        button.classList.remove("xtr-hero__copy--done")
      }, 2000)
    })
  })
})
