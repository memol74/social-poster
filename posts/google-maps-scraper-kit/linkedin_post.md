📍 How much time do you spend copy-pasting business leads off Google Maps?

Opening dozens of listings by hand, copying phone numbers and websites one at a time, then guessing at emails - it adds up fast.

Google Maps Scraper Kit is a free, open-source tool that runs the whole thing locally:

✅ Runs in Docker, no Google Maps API key required
✅ Pick a business type and city, like "dentists in Denver CO"
✅ Exports name, phone, email, website, category, address, rating and review count to CSV
✅ Visits business websites to find published emails, including contact/about pages
✅ Optional --socials flag adds Instagram, Facebook and LinkedIn links found on those sites
✅ Works via a dependency-free Python CLI, a local web UI, or a bundled Claude Code skill

2,038 stars, 399 forks, MIT licensed.

After cloning the repo and opening its folder:
docker compose up -d

Then run something like:
python3 scripts/scrape.py "dentists in Denver CO" --city "Denver, CO" --depth 5 --socials

Worth noting: Google's terms prohibit scraping and privacy laws apply to the contact data you collect, so use it carefully.

Would this save you hours on your next lead list? 👇
