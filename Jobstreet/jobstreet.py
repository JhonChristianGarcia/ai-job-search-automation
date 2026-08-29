import re
from pathlib import Path

from playwright.sync_api import sync_playwright, Page, expect, Locator

JOBSTREET_LINK = "https://ph.jobstreet.com/"
class Jobstreet:
    
    def __init__(self):
        self._playwright = None
        self._context = None
        self.page: Page | None = None

        #Page elements
        self.search: Locator | None = None
        self.seek_btn: Locator | None = None
        self.work_arrangement: Locator | None = None
        self.remote_option: Locator | None = None
        self.listing_time: Locator | None = None
        self.last_3_days_option: Locator | None = None
        
    def _persistent_browser_login(self):
        self._playwright = sync_playwright().start()

        user_data_dir = Path(
            r"C:\Users\xtian\AppData\Local\BraveSoftware\Brave-Browser\PlaywrightProfile"
        )

        executable_path = (
            r"C:\Program Files\BraveSoftware"
            r"\Brave-Browser\Application\brave.exe"
        )

        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            executable_path=executable_path,
            headless=False,
        )

        new_tab = self._context.new_page()

        for page in list(self._context.pages):
            if page != new_tab:
                page.close()
            
        self.page = self._context.new_page()

    def _wait_for_timeout(self, duration: int = 1):
        """Wait for network idle
        :param duration: Integer in seconds
        """
        self.page.wait_for_load_state('networkidle')
        self.page.wait_for_timeout(duration * 1000)

    def _click_outside_modal(self):
        self.page.locator("body").click(position={"x": 10, "y": 10})
    
    def goto_page(self):
        self._persistent_browser_login()

        self.page.goto(JOBSTREET_LINK)
        self.search = self.page.locator("#keywords-input")
        self.search.type("Typescript", delay=50)

        self.seek_btn = self.page.get_by_role("button", name="Submit search")
        expect(self.seek_btn).to_be_visible()
        self.seek_btn.click()

        self._wait_for_timeout()
        
        self.work_arrangement = self.page.locator("div").filter(has_text=re.compile(r"^RemoteRemote$")).nth(1)
        expect(self.work_arrangement).to_be_visible()
        self.work_arrangement.click()
        
        self.remote_option = self.page.get_by_role("checkbox", name="Remote")
        expect(self.remote_option).to_be_visible()
        self.remote_option.click()
        self._wait_for_timeout()
        
        self._click_outside_modal()

        self.listing_time = self.page.get_by_text("Show date listed refinements.Listing time").nth(1)
        expect(self.listing_time).to_be_visible()
        self.listing_time.click()

        self.last_3_days_option = self.page.get_by_role("radio", name="Last 3 days")
        expect(self.last_3_days_option).to_be_visible()
        self.last_3_days_option.click()
        self._wait_for_timeout()
        self._click_outside_modal() 

        jobs = self.page.get_by_test_id("job-list-item-link-overlay")
        assert jobs.count() > 1

        for i, job in enumerate(jobs.all(), start=1):
            if(i == 2):
                break
            job.click()
            self._wait_for_timeout(2)

            job_details_section = self.page.locator('[data-automation="jobDetailsPage"]')
            expect(job_details_section).to_be_visible()

            job_title_element = job_details_section.get_by_role("link").nth(0)
            if(job_title_element.inner_text() is None or job_title_element.inner_text() == ''):
                job_title_element = job_details_section.get_by_role("link").nth(1)
            job_description_section = job_details_section.locator('[data-automation="jobAdDetails"]')
            
            job_title = job_title_element.inner_text()
            job_description = job_description_section.inner_text()

            print({
                "job_title": job_title,
                "job_description": job_description
            })
            
        self.page.pause()
        self._clean_up()

    def _clean_up(self):
        if self._context:
            self._context.close()

        if self._playwright:
            self._playwright.stop()


if __name__ == "__main__":
    jobstreet = Jobstreet()

    try:
        jobstreet.goto_page()
    finally:
        print("Applied to 10 jobs")