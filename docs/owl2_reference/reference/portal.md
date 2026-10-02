<!-- Quelle: https://github.com/odoo/owl/blob/v2.8.4/doc/reference/portal.md · abgerufen 2026-10-02 -->

# 🦉 Portal 🦉

It is sometimes useful to be able to render some content outside the boundaries
of a component. To do that, Owl provides a special directive: `t-portal`:

```js
class SomeComponent extends Component {
  static template = xml`
      <div>this is inside the component</div>
      <div t-portal="'body'">and this is outside</div>
    `;
}
```

The `t-portal` directive takes a valid css selector as argument. The content of
the portalled template will be mounted at the corresponding location. Note that
Owl need to insert an empty text node at the location of the portalled content.
