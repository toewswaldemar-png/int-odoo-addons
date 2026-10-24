# Generic rules

* Order properties following the position - float - flex - display - size - margin - padding - border - background - font order (basically layout followed by style):
```scss
    .o_my_class {
        position: relative;
        @include o-flex(1, 1, auto);
        display: block;
        width: 200px;
        height: 150px;
        margin: 10px 25px;
        padding: 8px;
        border: 3px solid red;
        background: blue;
        font-size: 2px;
        // ...
    }
```
* Put a space between the selector and the opening `{`
* Use "full" property when possible (use `margin` instead of `margin-top`)
* Indentation should always be 4-spaces
* Be careful when using a `,` in a hierarchy:
```scss
    .o_class_a {
        .o_class_b, .o_class_c {
            .o_class_d {
                // ...
            }
        }
    }
```
Here, this will create only one CSS rule:
```scss
.o_class_a .o_class_b .o_class_d, .o_class_a .o_class_c .o_class_d {}
```
But you still have to make sure that you really wanted the rule to be applied in both `.o_class_a .o_class_b` AND `.o_class_a .o_class_c` contexts.

* Do not create complex LESS hierarchy for nothing; use this:
```scss
    .o_class_a .o_class_b .o_class_c {
        display: block;
        .o_class_d {
            margin-top: 4px;
        }
    }
```
instead of this:
```scss
    .o_class_a {
        .o_class_b {
            .o_class_c {
                display: block;
                .o_class_d {
                    margin-top: 4px;
                }
            }
        }
    }
```

# Mixins

* Use mixins when possible (see utils.scss file). In particular, there are mixins for the flex properties.
* Do not use the `square` mixin, the name is confusing.

# Flex

Flex is great but remember it is not a great idea to use it on every DOM element. While flex is now supported by every major browser, its behavior is somewhat different from one browser to another and this becomes even more visible when there is a deep hierarchy of flex elements in the page. Most of the time, the nearly same behavior that you want is possible without flex and will be more efficient without it.

# Styling

When you want to style some stuff, here are the steps you *must* follow:
1. Check if there is a standard Odoo (+ bootstrap) layout / set of classes that would style your DOM the way you want it. In that case, there is not any SCSS to declare. Just use the right layout and classes.
2. Check if there is an Odoo app which uses a style which looks the same as the one you want. If this is the case, there should be a way to share this style in a common app (even in web, check with the framework team).
3. If required, create a SCSS file for your app. Try to style only elements found by their classnames (avoid styling element found by ID or tag name). Classnames should follow the convention:
    - o_<app_name>_... where <app_name> is the name of your app (this is skipped for "standard" app like web and website)

If your app will need scss variables to control the style, you may want to split your scss files. Indeed, there are particular sub-assets templates that are designed to contain variables only. This would allow your app to be customized by a sub-application. Indeed, unlike in LESS, SCSS variables are not lazy loaded.

- `web._assets_utils`: regroups the mixins and functions which *can*
  (and so should) be available in every asset bundle

- `web._assets_primary_variables`: regroups the variables (or mixins
  used as variables) which *can* (and so should) be available in
  every asset bundle

- `web._assets_secondary_variables`: same as above but provides an
  environnement where all the 'primary' ones are accessible. This is
  for example useful to handle the community/enterprise split:

```scss
  // Community primary variables
  $o-pink-color: pink; // enterprise color
  $o-brand-primary: blue;

  // Enterprise primary variables
  $o-brand-primary: $o-pink-color;

  // Community secondary variables
  $o-my-darker-primary: darken($o-brand-primary, 5%);
```

  => If there was only one variable template, enterprise edition would
     have been able to define its primary color at the end but the
     darker primary would not have been updated. Using the `!default`
     system and putting enterprise definition above would not have
     solved the problem as the $o-pink-color would not have been
     accessible.

- `web._assets_backend_helpers`: regroups the variables, mixins and
  functions which *can* (and so should) be available in the backend
  asset bundle only. This is especially (only?) useful for bootstrap
  variables overriddes.

- `web._assets_frontend_helpers`: regroups the variables, mixins and
  functions which *can* (and so should) be available in the frontend
  asset bundle only. This is especially (only?) useful for bootstrap
  variables overriddes.

Note: bootstrap variables are not accessible in any of those anymore.
If you have variables that should depend on bootstrap, you have 3
solutions:

- Find another way: your variable is probably useless, use bootstrap
  variables directly or create a variable that will influence the
  value of bootstrap variables. E.g. instead of declaring:
  `$myvar: $bootstrapvar * 3`
  and using `$myvar` alone, declare:
  `$myvar: 3` and use `$myvar * $bootstrapvar` where needed.

- Declare a copy of the bootstrap variable and use that one. In that
  case, you should also force-set the real bootstrap one to be sure
  they match (this should be done in appropriate templates mentioned
  above). E.g.
  ```scss
  $o-boostrapvar: 5;
  ...
  $boostrapvar: $o-bootstrapvar;
  ```

- Set your variable to `null` and set it to your bootstrap expression
  in the file you will need it (where bootstrap variables are accessible)
  without forgetting to add the `!default` flag to allow overriddes.
  ```scss
  $myvar: null;
  ...
  $myvar: $bootstrapvar * 5 !default;
  ```