"""Quote model, built-in collection and quality filter.

The built-in collection is curated: every quote is attributed to the person
who actually said or wrote it, with a reference to the work, speech or letter
it comes from. Popular quotes that are misattributed or have no reliable
source (checked against Wikiquote, Quote Investigator, DBNL and the original
works) are deliberately left out.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

from .const import LANGUAGE_ALL, LANGUAGE_EN, LANGUAGE_NL, SOURCE_BUILTIN


@dataclass(frozen=True, slots=True)
class Quote:
    """A single quote."""

    text: str
    author: str
    language: str
    reference: str = ""
    source: str = SOURCE_BUILTIN

    @property
    def key(self) -> str:
        """Normalized text, used to detect duplicates across sources."""
        return normalize(self.text)

    def as_dict(self) -> dict[str, Any]:
        """Return the quote as a dict (for storage)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Quote:
        """Create a quote from a stored dict."""
        return cls(
            text=str(data["text"]),
            author=str(data.get("author") or ""),
            language=str(data.get("language") or LANGUAGE_EN),
            reference=str(data.get("reference") or ""),
            source=str(data.get("source") or SOURCE_BUILTIN),
        )


def normalize(text: str) -> str:
    """Lowercase letters and digits only, for duplicate detection."""
    return re.sub(r"[\W_]+", "", text.casefold())


# --- Quality filter for quotes from online sources ---------------------------

MIN_LENGTH = 15
MAX_LENGTH = 250
MAX_WORDS = 50

_BAD_AUTHORS = {"", "unknown", "anonymous", "anon", "author unknown", "n/a", "zenquotes.io"}
_URL_RE = re.compile(r"https?://|www\.|\.com\b|@|#\w")
_MARKUP_RE = re.compile(r"<[^>]+>|\[\[|\]\]|\{\{")


def is_good_quote(quote: Quote) -> bool:
    """Return True when an online quote is worth showing.

    Rejects quotes without a real author, that are too short or too long for a
    dashboard, that contain links, hashtags or markup, or that are shouting.
    """
    text = quote.text
    if quote.author.strip().casefold() in _BAD_AUTHORS:
        return False
    if not MIN_LENGTH <= len(text) <= MAX_LENGTH or len(text.split()) > MAX_WORDS:
        return False
    if _URL_RE.search(text) or _MARKUP_RE.search(text):
        return False
    letters = [c for c in text if c.isalpha()]
    if not letters or sum(c.isupper() for c in letters) > 0.5 * len(letters):
        return False
    return True


# --- Built-in collection -----------------------------------------------------


def _en(text: str, author: str, reference: str = "") -> Quote:
    return Quote(text, author, LANGUAGE_EN, reference)


def _nl(text: str, author: str, reference: str = "") -> Quote:
    return Quote(text, author, LANGUAGE_NL, reference)


BUILTIN_QUOTES: tuple[Quote, ...] = (
    # --- English: philosophy ---
    _en("The unexamined life is not worth living.", "Socrates", "Plato, Apology 38a"),
    _en(
        "The journey of a thousand miles begins with one step.",
        "Lao Tzu",
        "Tao Te Ching, ch. 64",
    ),
    _en(
        "Knowing others is intelligence; knowing yourself is true wisdom.",
        "Lao Tzu",
        "Tao Te Ching, ch. 33",
    ),
    _en(
        "What you do not want done to yourself, do not do to others.",
        "Confucius",
        "Analects 15.24",
    ),
    _en(
        "Waste no more time arguing about what a good man should be. Be one.",
        "Marcus Aurelius",
        "Meditations 10.16",
    ),
    _en(
        "Dwell on the beauty of life. Watch the stars, and see yourself running with them.",
        "Marcus Aurelius",
        "Meditations 7.47",
    ),
    _en(
        "The soul becomes dyed with the colour of its thoughts.",
        "Marcus Aurelius",
        "Meditations 5.16",
    ),
    _en(
        "We suffer more often in imagination than in reality.",
        "Seneca",
        "Letters to Lucilius, 13",
    ),
    _en(
        "It is not that we have a short time to live, but that we waste a lot of it.",
        "Seneca",
        "On the Shortness of Life, 1",
    ),
    _en("While we are postponing, life speeds by.", "Seneca", "Letters to Lucilius, 1"),
    _en(
        "He who has a why to live can bear almost any how.",
        "Friedrich Nietzsche",
        "Twilight of the Idols (1888)",
    ),
    _en(
        "What does not kill me makes me stronger.",
        "Friedrich Nietzsche",
        "Twilight of the Idols (1888)",
    ),
    _en("I think, therefore I am.", "René Descartes", "Discourse on the Method (1637)"),
    _en("Knowledge is power.", "Francis Bacon", "Meditationes Sacrae (1597)"),
    _en(
        "The limits of my language mean the limits of my world.",
        "Ludwig Wittgenstein",
        "Tractatus Logico-Philosophicus 5.6 (1921)",
    ),
    _en("One must imagine Sisyphus happy.", "Albert Camus", "The Myth of Sisyphus (1942)"),
    _en(
        "In the depths of winter, I finally learned that within me there lay an "
        "invincible summer.",
        "Albert Camus",
        "Return to Tipasa (1952)",
    ),
    _en(
        "The good life is one inspired by love and guided by knowledge.",
        "Bertrand Russell",
        "What I Believe (1925)",
    ),
    _en(
        "We are what we repeatedly do. Excellence, then, is not an act, but a habit.",
        "Will Durant",
        "The Story of Philosophy (1926)",
    ),
    _en(
        "Those who cannot remember the past are condemned to repeat it.",
        "George Santayana",
        "The Life of Reason (1905)",
    ),
    # --- English: science & technology ---
    _en(
        "Imagination is more important than knowledge.",
        "Albert Einstein",
        "Interview, The Saturday Evening Post (1929)",
    ),
    _en(
        "Life is like riding a bicycle. To keep your balance you must keep moving.",
        "Albert Einstein",
        "Letter to his son Eduard (1930)",
    ),
    _en(
        "Try not to become a man of success, but rather try to become a man of value.",
        "Albert Einstein",
        "LIFE magazine (1955)",
    ),
    _en(
        "The important thing is not to stop questioning.",
        "Albert Einstein",
        "LIFE magazine (1955)",
    ),
    _en(
        "If I have seen further it is by standing on the shoulders of giants.",
        "Isaac Newton",
        "Letter to Robert Hooke (1675)",
    ),
    _en(
        "The first principle is that you must not fool yourself, and you are the "
        "easiest person to fool.",
        "Richard Feynman",
        "Cargo Cult Science, Caltech commencement (1974)",
    ),
    _en(
        "What I cannot create, I do not understand.",
        "Richard Feynman",
        "On his blackboard at the time of his death (1988)",
    ),
    _en("We are a way for the cosmos to know itself.", "Carl Sagan", "Cosmos (1980)"),
    _en(
        "Extraordinary claims require extraordinary evidence.",
        "Carl Sagan",
        "Cosmos (1980)",
    ),
    _en(
        "Any sufficiently advanced technology is indistinguishable from magic.",
        "Arthur C. Clarke",
        "Profiles of the Future (1973 edition)",
    ),
    _en(
        "The best way to predict the future is to invent it.",
        "Alan Kay",
        "Xerox PARC meeting (1971)",
    ),
    _en(
        "Premature optimization is the root of all evil.",
        "Donald Knuth",
        "Structured Programming with go to Statements (1974)",
    ),
    _en(
        "Programs must be written for people to read, and only incidentally for "
        "machines to execute.",
        "Harold Abelson and Gerald Jay Sussman",
        "Structure and Interpretation of Computer Programs (1985)",
    ),
    _en(
        "Talk is cheap. Show me the code.",
        "Linus Torvalds",
        "Linux kernel mailing list (2000)",
    ),
    # --- English: speeches & public life ---
    _en(
        "The only thing we have to fear is fear itself.",
        "Franklin D. Roosevelt",
        "First inaugural address (1933)",
    ),
    _en(
        "Ask not what your country can do for you; ask what you can do for your country.",
        "John F. Kennedy",
        "Inaugural address (1961)",
    ),
    _en(
        "Darkness cannot drive out darkness; only light can do that. Hate cannot "
        "drive out hate; only love can do that.",
        "Martin Luther King Jr.",
        "Strength to Love (1963)",
    ),
    _en(
        "Education is the most powerful weapon which you can use to change the world.",
        "Nelson Mandela",
        "Speech at the launch of the Mindset Network (2003)",
    ),
    _en(
        "For to be free is not merely to cast off one's chains, but to live in a way "
        "that respects and enhances the freedom of others.",
        "Nelson Mandela",
        "Long Walk to Freedom (1994)",
    ),
    _en(
        "Do what you can, with what you have, where you are.",
        "Theodore Roosevelt",
        "An Autobiography (1913), quoting Squire Bill Widener",
    ),
    _en(
        "Not everything that is faced can be changed, but nothing can be changed "
        "until it is faced.",
        "James Baldwin",
        "As Much Truth As One Can Bear (1962)",
    ),
    _en(
        "Life is either a daring adventure or nothing.",
        "Helen Keller",
        "The Open Door (1957)",
    ),
    _en(
        "The only way to do great work is to love what you do.",
        "Steve Jobs",
        "Stanford commencement address (2005)",
    ),
    _en(
        "Stay hungry. Stay foolish.",
        "Steve Jobs",
        "Stanford commencement address (2005), quoting the Whole Earth Catalog",
    ),
    _en(
        "You miss 100% of the shots you don't take.",
        "Wayne Gretzky",
        "Interview with Bob McKenzie, The Hockey News (1983)",
    ),
    _en(
        "I can accept failure, everyone fails at something. But I can't accept not trying.",
        "Michael Jordan",
        "I Can't Accept Not Trying (1994)",
    ),
    # --- English: literature ---
    _en(
        "This above all: to thine own self be true.",
        "William Shakespeare",
        "Hamlet, act 1, scene 3",
    ),
    _en(
        "We know what we are, but know not what we may be.",
        "William Shakespeare",
        "Hamlet, act 4, scene 5",
    ),
    _en(
        "The fault, dear Brutus, is not in our stars, but in ourselves.",
        "William Shakespeare",
        "Julius Caesar, act 1, scene 2",
    ),
    _en(
        "Two roads diverged in a wood, and I, I took the one less traveled by, and "
        "that has made all the difference.",
        "Robert Frost",
        "The Road Not Taken (1916)",
    ),
    _en(
        "In three words I can sum up everything I've learned about life: it goes on.",
        "Robert Frost",
        "Interview with Ray Josephs (1954)",
    ),
    _en(
        "Hope is the thing with feathers that perches in the soul.",
        "Emily Dickinson",
        "Poem 254 (c. 1861)",
    ),
    _en(
        "If one advances confidently in the direction of his dreams, he will meet "
        "with a success unexpected in common hours.",
        "Henry David Thoreau",
        "Walden (1854)",
    ),
    _en(
        "Nothing great was ever achieved without enthusiasm.",
        "Ralph Waldo Emerson",
        "Circles (1841)",
    ),
    _en(
        "Trust thyself: every heart vibrates to that iron string.",
        "Ralph Waldo Emerson",
        "Self-Reliance (1841)",
    ),
    _en(
        "We are all in the gutter, but some of us are looking at the stars.",
        "Oscar Wilde",
        "Lady Windermere's Fan (1892)",
    ),
    _en(
        "To live is the rarest thing in the world. Most people exist, that is all.",
        "Oscar Wilde",
        "The Soul of Man under Socialism (1891)",
    ),
    _en(
        "Courage is resistance to fear, mastery of fear, not absence of fear.",
        "Mark Twain",
        "Pudd'nhead Wilson (1894)",
    ),
    _en(
        "The difference between the right word and the almost right word is the "
        "difference between lightning and a lightning bug.",
        "Mark Twain",
        "Letter to George Bainton (1888)",
    ),
    _en(
        "It is only with the heart that one can see rightly; what is essential is "
        "invisible to the eye.",
        "Antoine de Saint-Exupéry",
        "The Little Prince (1943)",
    ),
    _en(
        "Perfection is achieved, not when there is nothing more to add, but when "
        "there is nothing left to take away.",
        "Antoine de Saint-Exupéry",
        "Wind, Sand and Stars (1939)",
    ),
    _en(
        "Not all those who wander are lost.",
        "J.R.R. Tolkien",
        "The Fellowship of the Ring (1954)",
    ),
    _en(
        "All we have to decide is what to do with the time that is given us.",
        "J.R.R. Tolkien",
        "The Fellowship of the Ring (1954)",
    ),
    _en(
        "It does not do to dwell on dreams and forget to live.",
        "J.K. Rowling",
        "Harry Potter and the Philosopher's Stone (1997)",
    ),
    _en(
        "It is our choices that show what we truly are, far more than our abilities.",
        "J.K. Rowling",
        "Harry Potter and the Chamber of Secrets (1998)",
    ),
    _en(
        "A reader lives a thousand lives before he dies. The man who never reads "
        "lives only one.",
        "George R.R. Martin",
        "A Dance with Dragons (2011)",
    ),
    _en("Fear is the mind-killer.", "Frank Herbert", "Dune (1965)"),
    _en(
        "Never let your sense of morals prevent you from doing what is right.",
        "Isaac Asimov",
        "Foundation (1951)",
    ),
    _en(
        "There is no greater agony than bearing an untold story inside you.",
        "Maya Angelou",
        "I Know Why the Caged Bird Sings (1969)",
    ),
    _en(
        "A ship in harbor is safe, but that is not what ships are built for.",
        "John A. Shedd",
        "Salt from My Attic (1928)",
    ),
    _en(
        "Life is what happens to you while you're busy making other plans.",
        "John Lennon",
        "Beautiful Boy (Darling Boy) (1980)",
    ),
    _en("Do. Or do not. There is no try.", "Yoda", "The Empire Strikes Back (1980)"),
    # --- English: proverbs ---
    _en(
        "The best time to plant a tree was 20 years ago. The second best time is now.",
        "Chinese proverb",
    ),
    _en(
        "If you want to go fast, go alone. If you want to go far, go together.",
        "African proverb",
    ),
    _en("Fall seven times, stand up eight.", "Japanese proverb"),
    # --- Nederlands: Nederlandse en Vlaamse auteurs ---
    _nl("Elk nadeel heb z'n voordeel.", "Johan Cruijff"),
    _nl("Je gaat het pas zien als je het doorhebt.", "Johan Cruijff"),
    _nl(
        "Voetballen is heel simpel, maar het moeilijkste wat er is, is simpel voetballen.",
        "Johan Cruijff",
    ),
    _nl(
        "In het land der blinden is eenoog koning.",
        "Desiderius Erasmus",
        "Adagia (1500)",
    ),
    _nl(
        "Misschien is niets geheel waar, en zelfs dát niet.",
        "Multatuli",
        "Ideeën, idee 1 (1862)",
    ),
    _nl(
        "Tussen droom en daad staan wetten in de weg en praktische bezwaren.",
        "Willem Elsschot",
        "Het huwelijk (1910)",
    ),
    _nl(
        "Poëzie is een daad van bevestiging. Ik bevestig dat ik leef, dat ik niet "
        "alleen leef.",
        "Remco Campert",
        "Poëzie is een daad",
    ),
    _nl("Alles van waarde is weerloos.", "Lucebert", "De zeer oude zingt (1974)"),
    _nl(
        "Denkend aan Holland zie ik breede rivieren traag door oneindig laagland gaan.",
        "Hendrik Marsman",
        "Herinnering aan Holland (1936)",
    ),
    _nl("'t Kan verkeren.", "Gerbrand Adriaensz. Bredero", "Zinspreuk van Bredero"),
    _nl(
        "Alle edele dingen zijn even moeilijk als zeldzaam.",
        "Baruch Spinoza",
        "Ethica, slot (1677)",
    ),
    _nl(
        "Vrede is niet de afwezigheid van oorlog, maar een deugd die voortkomt uit "
        "de kracht van de geest.",
        "Baruch Spinoza",
        "Tractatus Politicus, hfdst. 5 (1677)",
    ),
    _nl(
        "Ik wil nog voortleven, ook na mijn dood!",
        "Anne Frank",
        "Dagboek, 5 april 1944",
    ),
    # --- Nederlands: vertaalde klassiekers ---
    _nl("Ik denk, dus ik ben.", "René Descartes", "Discours de la méthode (1637)"),
    _nl(
        "Een reis van duizend mijl begint met één stap.",
        "Lao Tzu",
        "Tao Te Ching, hfdst. 64",
    ),
    _nl(
        "Verspil geen tijd meer met discussiëren over wat een goed mens is. Wees er een.",
        "Marcus Aurelius",
        "Overpeinzingen 10.16",
    ),
    _nl(
        "Terwijl we uitstellen, snelt het leven voorbij.",
        "Seneca",
        "Brieven aan Lucilius, 1",
    ),
    _nl(
        "Wie een waarom heeft om voor te leven, kan bijna elk hoe verdragen.",
        "Friedrich Nietzsche",
        "Afgodenschemering (1888)",
    ),
    _nl(
        "Verbeelding is belangrijker dan kennis.",
        "Albert Einstein",
        "Interview, The Saturday Evening Post (1929)",
    ),
    _nl(
        "Als ik verder heb gezien, is dat omdat ik op de schouders van reuzen stond.",
        "Isaac Newton",
        "Brief aan Robert Hooke (1675)",
    ),
    _nl(
        "Alleen met het hart kun je goed zien. Het wezenlijke is voor de ogen onzichtbaar.",
        "Antoine de Saint-Exupéry",
        "De kleine prins (1943)",
    ),
    _nl(
        "We liggen allemaal in de goot, maar sommigen van ons kijken naar de sterren.",
        "Oscar Wilde",
        "Lady Windermere's Fan (1892)",
    ),
    _nl(
        "Duisternis kan duisternis niet verdrijven; alleen licht kan dat. Haat kan "
        "haat niet verdrijven; alleen liefde kan dat.",
        "Martin Luther King Jr.",
        "Strength to Love (1963)",
    ),
    _nl(
        "Midden in de winter ontdekte ik eindelijk dat er in mij een onoverwinnelijke "
        "zomer was.",
        "Albert Camus",
        "Terugkeer naar Tipasa (1952)",
    ),
    _nl(
        "Het leven is wat je overkomt terwijl je druk bezig bent andere plannen te maken.",
        "John Lennon",
        "Beautiful Boy (Darling Boy) (1980)",
    ),
    # --- Nederlands: spreekwoorden ---
    _nl("Wie niet waagt, die niet wint.", "Spreekwoord"),
    _nl("Al doende leert men.", "Spreekwoord"),
    _nl("Rome is niet in één dag gebouwd.", "Spreekwoord"),
    _nl("Beter een goede buur dan een verre vriend.", "Spreekwoord"),
    _nl("Oost west, thuis best.", "Spreekwoord"),
    _nl("Na regen komt zonneschijn.", "Spreekwoord"),
    _nl("Wie het kleine niet eert, is het grote niet weerd.", "Spreekwoord"),
    _nl("Zachte heelmeesters maken stinkende wonden.", "Spreekwoord"),
    _nl("Eendracht maakt macht.", "Spreekwoord"),
    _nl("Een goed begin is het halve werk.", "Spreekwoord"),
    _nl("Het geluk zit in een klein hoekje.", "Spreekwoord"),
    _nl("Gedeelde vreugde is dubbele vreugde, gedeelde smart is halve smart.", "Spreekwoord"),
)


def quotes_for_language(language: str) -> tuple[Quote, ...]:
    """Return the built-in quotes for a language (or all of them)."""
    if language == LANGUAGE_ALL:
        return BUILTIN_QUOTES
    selected = tuple(q for q in BUILTIN_QUOTES if q.language == language)
    return selected or BUILTIN_QUOTES
