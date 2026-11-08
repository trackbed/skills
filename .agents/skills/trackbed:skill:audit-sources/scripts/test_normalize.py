#!/usr/bin/env python3

from __future__ import annotations

import unittest

from normalize import normalize_html


class NormalizeHtmlTests(unittest.TestCase):
    def test_void_tag_inside_skipped_region_does_not_extend_skip(self) -> None:
        raw = "<nav><img><p>drop</p></nav><p>keep</p>"

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_void_end_tag_inside_skipped_region_does_not_end_skip(self) -> None:
        raw = '<nav><input></input><a href="/leak">drop</a></nav><p>keep</p>'

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_unclosed_list_items_inside_skipped_region_do_not_extend_skip(self) -> None:
        raw = '<nav><ul><li><a href="/a">drop</a><li>drop</ul></nav><h1>Title</h1><p>keep</p>'

        self.assertEqual(normalize_html(raw), "# Title\n\nkeep\n")

    def test_unclosed_paragraphs_inside_chrome_div_do_not_extend_skip(self) -> None:
        raw = '<div class="sidebar"><div><p>drop<p>drop</div></div><p>keep'

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_unclosed_chrome_list_items_end_at_parent_list_end_tag(self) -> None:
        raw = '<ul><li class="menu-item">drop<li class="menu-item">drop</ul><p>keep</p>'

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_unclosed_structural_root_ends_at_enclosing_end_tag(self) -> None:
        raw = "<div><nav>drop</div><p>keep</p>"

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_stray_end_tag_inside_skipped_region_does_not_end_skip(self) -> None:
        raw = "<nav><div>a</div></div><p>drop</p></nav><p>keep</p>"

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_enclosing_end_tag_that_ends_skip_is_still_processed(self) -> None:
        raw = '<p><a href="/x">Docs<span class="menu">x</a> after</p>'

        self.assertEqual(normalize_html(raw), "[Docs](/x) after\n")

    def test_end_tag_for_element_closed_before_skip_does_not_end_skip(self) -> None:
        raw = "<div>x</div><nav><div>a</div></div><p>drop</p></nav><p>keep</p>"

        self.assertEqual(normalize_html(raw), "x\n\nkeep\n")

    def test_end_tag_closes_unclosed_children_before_skip(self) -> None:
        raw = "<div><p>a</div><nav></p>drop</nav><p>keep</p>"

        self.assertEqual(normalize_html(raw), "a\n\nkeep\n")

    def test_end_tag_closes_inner_element_before_enclosing_one(self) -> None:
        raw = "<div><nav><div>menu</div>drop</nav></div><p>keep</p>"

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_void_end_tag_does_not_match_void_tag_before_skip(self) -> None:
        raw = "<br><nav></br>drop</nav><p>keep</p>"

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_unclosed_children_inside_stripped_element_do_not_extend_skip(self) -> None:
        raw = '<svg><path d="M0"></svg><p>keep</p>'

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_nested_root_tag_inside_skipped_region_keeps_skip_open(self) -> None:
        raw = "<nav><nav><p>drop</p></nav><p>drop</p></nav><p>keep</p>"

        self.assertEqual(normalize_html(raw), "keep\n")

    def test_utility_class_tokens_do_not_drop_page_content(self) -> None:
        raw = (
            '<div class="grid min-h-(--fd-docs-height) [--fd-header-height:0px] [--fd-sidebar-width:0px]">'
            "<main><h1>Guide</h1><p>Body text</p></main></div>"
        )

        self.assertEqual(normalize_html(raw), "# Guide\n\nBody text\n")

    def test_plain_chrome_class_and_id_names_still_drop(self) -> None:
        raw = (
            '<div class="site-header">drop</div><div id="main-nav">drop</div>'
            '<div class="md:hidden cookie-banner">drop</div><p>keep</p>'
        )

        self.assertEqual(normalize_html(raw), "keep\n")


if __name__ == "__main__":
    unittest.main()
