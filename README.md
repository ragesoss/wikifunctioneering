Hi!

This repo is basically me vibe-coding my way through understanding and contributing to Wikifunctions. (This is probably the only human-written file.)

It's a collection of scripts, context docs, and other stuff — probably only relevant if you have functioneer rights on Wikifunctions — that I've used to wrap my head around how to build composition functions at understandable levels of abstraction, and use functions to explore the modeling of Wikidata (which has alway been a struggle for me to understand, without working code to validate one approach to modeling a domain vs another). I've also been saving session notes to document the things I've worked on and how understanding of Wikifunctions embodied in this repo has evolved.

I've found Claude Code to be good at this, because it can easily find solutions to the "plumbing" problems of how to get from one object or datapoint to another, if I explain in plain language what I want a function to do in relation to related Wikidata items and properties. You can probably just fork this repo and start a `claude` session (or some other AI coding agent), and have some useful starting points and utility functions for whatever you're attempting on Wikifunctions.

Some of the interesting bits:
* A userscript I forked from `User:Feeglgeef/wikilambda_editsource.js`, which streamlines creating and updating zobjects, along with a set of browser scripts for preparing edits (and waiting for the functioneer to click publish)
* A system for downloading and caching every zobject in Wikifunctions to that we can `grep` them locally when searching for existing functions that do what we want. (As of April 2026, there are few enough that it's easy and quick to just get every one of them.)
* Guidelines for drafting and testing complex compositions via API calls, so you can easily see whether the composition you want will actually work and test it against lots of examples, before trying to add new functions or tests.

This is good for exploring Wikidata as well. You can compose a function, then test it with a whole series of relevant Wikidata items to see which ones are modeled in a compatible way and which ones should be updated.