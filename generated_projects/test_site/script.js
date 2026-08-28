```javascript
document.addEventListener('DOMContentLoaded', function() {
    const heroSection = document.querySelector('.hero');
    const descriptionSection = document.querySelector('.description');
    const ctaBtn = document.querySelector('.cta-btn');

    // Function to show the description section when the hero section is clicked
    function showDescription() {
        heroSection.style.display = 'none';
        descriptionSection.style.display = 'block';
    }

    // Adding click event listener to the hero section
    heroSection.addEventListener('click', showDescription);

    // Function to hide the description section and show the hero section
    function hideDescription() {
        heroSection.style.display = 'block';
        descriptionSection.style.display = 'none';
    }

    // Adding click event listener to the button
    ctaBtn.addEventListener('click', hideDescription);
});
```