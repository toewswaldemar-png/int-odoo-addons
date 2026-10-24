Reporting Issues
----------------
1. Make sure you've actually read the error message if there is one, it may really help
2. No need to create an issue if you're [making a PR](#making-pull-requests) to fix it. Describe the issue in the PR, it's the same as an issue, but with higher priority!
2. Double-check that the issue still occurs with the latest version of Odoo (you can easily test this on [Runbot](http://runbot.odoo.com))
3. [Search](https://github.com/odoo/odoo/issues) for similar issues before reporting anything
4. If you're not sure it's a bug, search in [Odoo Help](https://www.odoo.com/forum/1) or ask a question there to find out
5. If you're a programmer, try investigating/fixing yourself, and consider making a Pull Request instead
6. If you really think a new issue is useful, keep in mind that it will be treated with a much lower priority than a Pull Request or an Odoo Enterprise support ticket

**⚠** If you think you need to report a **security vulnerability**, please see our [Responsible Disclosure](https://www.odoo.com/page/responsible-disclosure) page. Our security issues archive can be found [here](https://github.com/odoo/odoo/issues?q=is%3Aissue+label%3ASecurity).

If later on you create a pull request solving an opened issue, do not forget to reference it in your pull request (e.g.: "This patch fixes issue #42").

When reporting an issue or creating a pull request, please **use the following template**:

```
**Quantity field is ignored in a sale order**

Impacted versions:
 
 - 20.0
 
Steps to reproduce:
 
 1. create a new sale order
 2. add a line with product 'Service', quantity 2, unit price 10.0
 3. validate the sale order
 
Current behavior:
 
 - Total price of 10.0
 
Expected behavior:
 
 - Total price of 20.0 (2 * 10 = 20)
```

For web or rendering issues, do not forget to specify the operating system and browser you are using.

When appropriate please provide screenshots and/or screencast demonstrating the issue.

Don't forget that a bug obvious to you may not be to others (maybe not using the same modules, etc.), **don't neglect reproducing conditions** !

## Tracebacks

If you have a code error (a.k.a. traceback), do include it in your bug report using code marks (not a screenshot!).

    ```
    Traceback (most recent call last):
    ...
    ```
If you are reporting some client-side failure and you include client-side logs, **you must enable the developer mode with assets before you paste the logs**:

* Go to `Settings > Activate the developer mode (with assets)`.

Otherwise, your logs would come from the compressed version of the ECMAScript (a.k.a. JavaScript) sources, which means they would be **completely useless**.

Making Pull Requests
--------------------
1. Make sure you target [the right branch](#against-which-version-should-i-submit-a-patch)
2. Keep your changes minimal, and strictly related to your issue (make other PRs if needed)
3. Match the style of the surrounding code, in terms of whitespace, wrapping, etc.
4. There are restrictions on the kind of [changes allowed in stable series](#what-does-stable-mean)
5. Explain **why** you are doing a change, not **what** (should be understandable from the diff)
6. If not done already, [sign the CLA](https://www.odoo.com/sign-cla) in your PR
7. Do not use Pull Requests to update translations, this is done using [an external system](https://github.com/odoo/odoo/wiki/Translations)
8. Minimal commits! Rebase and squash your changes whenever you modify your PR and before submitting
9. No conflicts! Rebase off the target branch just before submitting
10. After [Runbot](http://runbot.odoo.com/runbot) verifies your PR, fix anything that breaks the tests
11. [Write a test](https://www.odoo.com/documentation/master/developer/reference/backend/testing.html) to reproduce the issue if possible. Not mandatory in all cases but it will speedup the review if needed.

Against which version should I submit a patch?
----------------------------------------------

|What                              |17.0|18.0|19.0|20.0|master|
|----------------------------------|----|---|----|----|------|
|Bug fix                           |❌   |✓  |✓   |✓   |❌     |
|Localizations                     |❌   |✓  |✓   |✓   |✓     |
|Unstable change/Feature Request   |❌   |❌  |❌   |❌   |✓     |


**Important:** **Please do NOT create pull requests with the same patch on multiple target branches.**
Fixes made in LTS versions (currently 18.0, 19.0, 20.0) will be forward ported to upper versions. 



What does "Stable" mean?
------------------------
Changes in stable series must respect these guidelines:
* Keep changes to a minimum: stable patches must have a good value/risk ratio. If risk is too high or value too low, it must not be merged at all in stable (rather in the development series)
* No "improvement" (technical or functional) should be done in stable, they typically have a very low value/risk ratio. Often, the functional coverage is voluntarily limited.
* No purely cosmetic changes (formatting, pep8, etc.)
* No change in the signature of public methods on model (methods not starting with an underscore), as they are part of the public API used by integrated systems
* No change in the signature of private methods as much as possible, as they can be overridden in extension modules, which will easily break when the signature changes.
* No data model change: stored columns definitions must not be altered in incompatible manners under any circumstances (no addition / removal / incompatible type change)
* Limited, compatible changes such as changing `ondelete` rules or `size` parameters are allowed when necessary.
* For non-compatible change, in extreme cases an extra auto-install module could be added in order to automatically patch new installations without breaking existing ones
* No change to the XML IDs of existing module data, and no deletion of module data records that may be referenced by user data in existing databases, unless the changes are absolutely essential and the records were in `noupdate` mode initially.
* Non-stored function fields may be added if it is really necessary.
* XML files (views, menus, default data, etc.) should only be changed if inevitable. When changed, the change must not be mandatory, i.e. the Python code must not depend on the change.
* It is fine if a bugfix requires an explicit update, as long as it is safe for users who are not aware of it and do not perform the update.
* Critical security fixes must not depend on an explicit module update to take effect, they must work with a simple pull + restart
* Introducing new source terms (error messages, mail templates, view elements, etc.) should be reflected in the source terms of the module as explained [here](https://github.com/odoo/odoo/wiki/Translations#is-it-possible-to-modify-source-terms-in-odoo)

How can I translate Odoo in my language?
----------------------------------------
The translations are managed on a different platform than GitHub and synchronized periodically. Do not create pull requests to change the translations.

The translations are currently handled in [Odoo's Weblate instance](https://translate.odoo.com/). See [Translations](https://github.com/odoo/odoo/wiki/Translations) page for details.

How should I handle translatable content?
-----------------------------------------
In **stable versions**:
* You MUST NOT modify existing terms (even to fix a typo) unless absolutely necessary as it would break existing translations for people fetching the new source code.
* You MAY add or delete existing terms, but note that existing databases will need to update the language in their database to load the translation when its translation is completed and synced. New terms are auto-exported and synchronized weekly, so pot file updates SHOULD NOT be part of your pull request unless you are modifying a module not listed in [Odoo's Weblate instance](https://translate.odoo.com/).

Corrections of the source terms should only be done in master version. If you want to correct a message in stable version (e.g. correct a typo), you can create a English -> English translation.

New releases will have a stabilization period of a couple of month when modifications of source terms is tolerated.

How can I improve the documentation?
------------------------------------

[Odoo documentation](https://odoo.com/documentation) is managed on a [dedicated repository](https://github.com/odoo/documentation).
Please report issues and suggest improvements related to the documentation there.

Why was my issue closed without merging?
----------------------------------------

A pull request is closed when it will not be merged into odoo. This will typically happens if the fix/issue:

* is not relevant to Odoo development (label *invalid*)
* is not considered as a bug or we have no plan to change the current behavior (label *wontfix*)
* is a duplicate of another opened issue (label *duplicate*)
* the pull request should be resubmitted against another version

What is this Odoo-dev repository? Should I use it?
--------------------------------------------------

The `odoo-dev/odoo` repository is an internal repository used by the R&D of Odoo to keep the main repository clean. If you are coming from Launchpad, this is the equivalent of the `~openerp-dev` repository.

When forking Odoo to submit a patch, always use the `github.com/odoo/odoo` repository. Be also careful of the version you are branching as it will determine the history once the pull request will be realized (e.g.: `git checkout -b 18.0-my-branch odoo/18.0`).


Meaning of labels
-----------------

- **blocked**: a fix or information from the author of the request is required before merging
- **confirmed**: issue was validated by qualification team
- **Internationalization**: PR or issue about translating Odoo correctly
- **Localization**: PR or issue about adapting Odoo to local rules (mainly the chart of accounts)
- **need review**: a second level of review is required
- **Packaging**: PR or issue regarding packaged distributions of Odoo (.deb, .rpm, .exe, ...)
- **RFC**: Reserved label for Odoo asking feedback, usually for localization
- **Security**: Reserved label for security announcements
- **Web editor**: PR or issue related to the drag & drop website editor
- **Wishlist**: new feature, to discuss whether it will be integrated
- **Accounting**: PR or issue for the accounting team
- **Discuss**: PR or issue for the discuss team (channels, livechat, chatter)
- **eCommerce**: PR or issue for the eCommerce team (website_sale)
- **Framework**: PR or issue for the javascript framework team (web client)
- **Human Resources**: PR or issue for the HR team (hr_*, lunch, ...)
- **Logistics**: PR or issue for the logistic team (stock, MRP, purchase, quality, repair..)
- **Marketing**: PR or issue for the marketing team (mass_mailing, elearning, events, crm, ...)
- **ORM**: PR or issue for the python framework team (ORM)
- **Payment**: PR or issue for the payment team (payment and its associated APIs)
- **Point of Sale**: PR or issue for the POS team (point_of_sale and its corresponding pos_* APIs)
- **Sales**: PR or issue for the Sales team
- **Services**: PR or issue for the services team (project, timesheet, planning, ...)
- **Studio**: PR or issue for the studio team
- **Website**: PR or issue for the website team (all website_* modules except website_slides and website_event)
- **VoIP**: PR or issue for the VoIP team

##### Special labels (bots)

- **RD**: Internal pull request, by Odoo R&D team.
- **OE**: PR created to solve an Odoo enterprise ticket
- **CI**: PR passed the runbot tests

Credits
-------
[<img src="https://user-images.githubusercontent.com/9530767/27920397-b29533f6-6274-11e7-9e03-cc392526a6b8.png" alt="BrowserStack Logo" height="30">](http://www.browserstack.com)

Odoo uses [BrowserStack](http://www.browserstack.com) for cross-browser integration tests.