#!/usr/bin/env python
from __future__ import print_function
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from datetime import datetime, timedelta
from argparse import ArgumentParser
from time import sleep
import getpass
import sys
if sys.version[0] == '3': raw_input=input   # for python 2/3 cross compatibility

class Eraser(object):
    """
    Eraser class to remove Facebook content
    Set up, log in, go to activity page, then repeat delete
    If having trouble, use scroll down method or increase wait time
    Don't forget to quit in the end
    """

    def __init__(self, email, password, wait=1, dry_run=False, days=0, count=None):
        """
        Set up the eraser
        :return: Null
        """
        self.driver = webdriver.Firefox()
        self.email = email
        self.password = password
        self.profile_name = None            # this will end up being the facebook user name
        self.deleted_count = 0                      # counter of number of elements deleted
        self.hidden_count = 0                      # counter of number of elements deleted
        self.wait = wait
        self.post_css_selector = '.pam.bottomborder'
        self.dry_run = dry_run
        self.delete_background_color = '#e74c3c' # red
        self.hide_background_color = '#f39c12' # orange
        self.error_background_color = '#bdc3c7' # gray
        self.skip_background_color = '#1abc9c' # green
        self.timestamp_selector = 'tbody .clearfix span a'
        self.days = days
        self.menu_selector = '.uiContextualLayerPositioner.uiLayer'
        self.dialog_selector = '//div[@role="dialog"]'
        self.years_selector = '[data-year] > a'
        self.handled_posts = {}
        self.posts_to_delete = count

    def done(self):
        if self.total_purged() == self.posts_to_delete:
            return True

    def total_purged(self):
        return self.hidden_count + self.deleted_count

    def quit(self):
        """
        Quit the program (close out the browser)
        :return: Null
        """
        self.driver.quit()

    def login(self):
        """
        Log in to Facebook, set profile name
        :return: Null
        """
        self.driver.get('https://www.facebook.com/login/')
        email_element = self.driver.find_element_by_id('email')
        email_element.send_keys(self.email)
        password_element = self.driver.find_element_by_id('pass')
        password_element.send_keys(self.password)
        password_element.submit()

        if not self.wait_for_element('//a[@title="Profile"]'):
            print('Timeout while waiting for profile element')
            return

        profile_link = self.driver.find_element_by_css_selector('a[title="Profile"]')

        # link appears as http://www.facebook.com/PROFILE
        self.profile_name = profile_link.get_attribute('href')[25:]

    def go_to_activity_page(self):
        """
        Go to the activity page and prepare to start deleting
        :return: Null
        """
        if not self.profile_name:
            # the user hasn't logged in properly
            sys.exit(-2)
        # go to the activity page (filter by 'Your Posts')
        activity_link = 'https://www.facebook.com/' + self.profile_name + '/allactivity?privacy_source=activity_log&log_filter=cluster_11'
        self.driver.get(activity_link)
        sleep(self.wait)

    def scroll_down(self):
        """
        Executes JS to scroll down on page.
        Use if having trouble seeing elements
        :return:
        """
        self.driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        more_activity = self.wait_for_element('//a[@class="pam uiBoxLightblue uiMorePagerPrimary"]')
        if not more_activity:
            print('Timeout while waiting for "More Activity" button to show')
            return False

        return more_activity

    def scroll_to_element(self, element):
        self.driver.execute_script('var rect = arguments[0].getBoundingClientRect(); var sub = 0; if (rect.bottom > 700) { sub = -1000; } window.scrollTo(0, rect.bottom + sub);', element)

    def scroll_to_top(self):
        self.driver.execute_script('window.scrollTo(0, 0);')

    def click(self, element):
        self.driver.execute_script('arguments[0].click()', element)


    def wait_for_element(self, xpath, visible=False, driver=None):
        """
        Waits for an element to be present on the page. Has a timeout
        of 5 seconds. Returns a boolean indicating whether or not the
        element was shown.
        """
        if driver is None:
            driver = self.driver

        try:
            # 5 second delay for waiting until profile element shows
            delay = 2
            if not visible:
                element = WebDriverWait(driver, delay).until(EC.presence_of_element_located((By.XPATH, xpath)))
            else:
                element = WebDriverWait(driver, delay).until(EC.visibility_of_element_located((By.XPATH, xpath)))

            return element
        except TimeoutException:
            print('Timeout')
            pass

        return None


    def delete_posts(self):
        """
        Find the first available element and delete it
        :return: Null
        """

        count = 0
        posts = self.driver.find_elements_by_css_selector(self.post_css_selector)
        menu_indicators = [
            'Edit',
            'Highlighted on timeline',
            'Allowed on timeline',
            'Shown on timeline',
            'Hidden from timeline',
        ]

        purge_indicators = [
            (self.delete_background_color, 'Delete'),
            (self.hide_background_color, 'Hidden from timeline'),
        ]

        now = datetime.now() - timedelta(days=self.days)
        for post in posts:
            if post.id in self.handled_posts:
                continue

            self.handled_posts[post.id] = True
            date_element = None
            try:
                date_element = post.find_element_by_css_selector(self.timestamp_selector)
            except:
                pass

            if date_element is None and self.days != 0:
                print('No timestamp element found -- skipping to be safe')
                self.set_color(post, self.error_background_color)
                continue

            timestamp = datetime.strptime(date_element.get_attribute('textContent').strip(), '%b %d, %Y %I:%M%p')
            if timestamp > now:
                print('Too recent -- skipping')
                self.set_color(post, self.skip_background_color)
                continue

            while True:
                # Find the button that pops the remove from timeline/delete menu
                menu_button = None
                try:
                    menu_button = post.find_element_by_xpath('./table/tbody/tr/td[3]/div/div[2]/a')
                except:
                    pass

                if menu_button is None:
                    print('No matching menu button found for {}'.format(str(post)))
                    self.set_color(post, self.error_background_color)
                    return

                while True:
                    try:
                        self.click(menu_button)
                    except:
                        sleep(1)
                        continue

                    break

                self.set_color(menu_button, 'red')

                purge_menu = None
                purge_button = None
                purge_background = None
                delete = False
                selector = None

                purge_menus = self.driver.find_elements_by_css_selector(self.menu_selector)
                for menu in purge_menus:
                    if not 'hidden_elem' in menu.get_attribute('class'):
                        purge_menu = menu
                        break


                for indicator in purge_indicators:
                    try:
                        selector = './/span[contains(text(), "{text}")]'.format(text=indicator[1])
                        purge_button = purge_menu.find_element_by_xpath(selector)
                    except:
                        pass

                    if purge_button:
                        if indicator == purge_indicators[0]:
                            delete = True
                        purge_background = indicator[0]
                        break

                if purge_button is None:
                    print('No purge button found for {}'.format(str(post)))
                    self.set_color(post, self.error_background_color)

                    sleep(2)

                    continue
                else:
                    break

            print('[*] Purging element...')
            while True:
                try:
                    self.click(purge_button)
                except:
                    sleep(1)
                    continue

                break

            dialogs = self.driver.find_elements_by_xpath(self.dialog_selector)
            confirm_dialog = None
            for dialog in dialogs:
                if dialog.get_attribute('id') == 'fbRequestsFlyout':
                    continue

                confirm_dialog = dialog
                break

            print('[*] Finding purge button...')
            while True:
                sleep(2)
                if not self.dry_run:
                    element = self.wait_for_element('//button[contains(@class, "layerConfirm")]', visible=True)
                    if not element:
                        print('Confirmation layer never showed')
                        purge_background = self.error_background_color
                    else:
                        self.click(element)
                        break
                else:
                    print('[*] [DRY-RUN] Canceling element purge...')
                    element = self.wait_for_element('//a[contains(@class, "layerCancel")]', visible=True)
                    if not element:
                        print('Cancel layer never showed')
                        purge_background = self.error_background_color
                    else:
                        self.click(element)
                        break
            sleep(2)

            if self.dry_run:
                self.set_color(post, purge_background)

            if delete:
                self.deleted_count += 1
                print('[+] Element deleted ({count} in total)'.format(count=self.deleted_count))
            else:
                self.hidden_count += 1
                print('[+] Element hidden ({count} in total)'.format(count=self.hidden_count))

            count += 1
            if self.done():
                return count

        return count


    def set_attribute(self, element, attribute, value):
        self.driver.execute_script("arguments[0].setAttribute('{}', '{}')".format(attribute, value), element)

    def set_color(self, element, value):
        self.set_attribute(element, 'style', 'background-color: {}'.format(value))

    def load_activity(self):
        years = self.driver.find_elements_by_css_selector(self.years_selector)
        for year in years:
            self.click(year)
            sleep(self.wait)

        fail_count = 0

        while True:
            if self.done():
                print('Done!')
                break

            if fail_count >= 3:
                print('Something went wrong -- exiting')
                break

            sleep(self.wait)
            scroll_result = self.scroll_down()
            if not scroll_result:
                fail_count += 1
                continue
            else:
                try:
                    self.click(scroll_result)
                except:
                    fail_count += 1
                    continue

                fail_count = 0

            sleep(self.wait)


if __name__ == '__main__':
    """
    Main section of script
    """
    # set up the command line argument parser
    parser = ArgumentParser(description='Delete your Facebook activity.  Requires Firefox')
    parser.add_argument('--wait', type=float, default=3, help='Explicit wait time between page loads (default 1 second)')
    parser.add_argument('--dry', action='store_true', default=False, help='Do a dry run (just show what would be deleted)')
    parser.add_argument('--days', type=int, default=0, help='Delete posts that were made after the given number of days (default 0)')
    parser.add_argument('--count', type=int, default=None, help='Number of elements to delete (default all elements)')

    args = parser.parse_args()

    # execute the script
    email = raw_input("Please enter Facebook login email: ")
    password = getpass.getpass()
    eraser = Eraser(email=email, password=password, wait=args.wait, dry_run=args.dry, days=args.days, count=args.count)
    eraser.login()

    while True:
        eraser.go_to_activity_page()

        eraser.load_activity()

        days = args.days
        print ('[*] Trying to delete elements made more than {} days ago'.format(days))
        if args.dry:
            print('[*] Doing a dry run')
        if eraser.delete_posts() == 0:
            break


    print('Deleted {} elements and made {} not visible on your timeline'.format(eraser.deleted_count, eraser.hidden_count))
